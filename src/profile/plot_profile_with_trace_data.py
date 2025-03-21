import argparse
import os
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List
import math
from plot_profile_utils import load_profile_data, get_processed_df

DEFAULT_SERVICE_NAME = "nginx-web-server"

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Jaeger trace data for a given service.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Test configuration")
    parser.add_argument("--profile-data-dir", type=str, required=True, help="Profile Data directory")
    parser.add_argument("--trace-data-dir", type=str, required=True, help="Traces Data directory")
    parser.add_argument("--samples", type=int, default=10, help="Number of samples per operation")
    parser.add_argument("--plot-dir", type=str, default="outputs", help="Output directory for plots")
    parser.add_argument("--default-service-name", type=str, help="Default service name for traces")
    parser.add_argument("--save-trace-profile-csvs", type=bool, default=False, help="Save trace profile CSVs")
    parser.add_argument("--trace-profile-csv-dir", type=str, help="Output directory for CSV data")

    return parser.parse_args()

def load_traces_data(
    data_dir: str,
    service_name_for_traces: str,
    test_name: str,
    config: str,
    container_name: str
) -> pd.DataFrame:
    global DEFAULT_SERVICE_NAME

    jaeger_traces_csv_file_path: str = os.path.join(data_dir, 
                                                    f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    if not os.path.exists(jaeger_traces_csv_file_path):
        print(f"File not found: {jaeger_traces_csv_file_path}, trying default service name: {DEFAULT_SERVICE_NAME}")
        jaeger_traces_csv_file_path: str = os.path.join(data_dir, 
                                                    f"{DEFAULT_SERVICE_NAME}_{test_name}_{config}_traces_data.csv")

    jaeger_traces_df: pd.DataFrame = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df: pd.DataFrame = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    return container_jaeger_traces_df

def get_non_overlapping_longest_duration_traces(traces_df: pd.DataFrame) -> pd.DataFrame:
    result_rows = []
    
    for trace_id in traces_df['trace_id'].unique():
        trace_data = traces_df[traces_df['trace_id'] == trace_id].copy()
        trace_data = trace_data.sort_values(by='duration', ascending=False)
        
        selected_spans = []
        
        for _, row in trace_data.iterrows():
            start_time = row['start_time']
            end_time = row['end_time']
            
            overlaps = False
            for span_start, span_end in selected_spans:
                if not (end_time <= span_start or start_time >= span_end):
                    overlaps = True
                    break
            
            if not overlaps:
                selected_spans.append((start_time, end_time))
                result_rows.append(row)
    
    if not result_rows:
        return pd.DataFrame()
    
    return pd.DataFrame(result_rows)

def plot_aligned_median_resource_usage(
    traces_df: pd.DataFrame, 
    core_to_profile_data_df: Dict[str, pd.DataFrame],
    output_dir: str, 
    config: str, 
    container_name: str, 
    service_name_for_traces: str
) -> None:
    non_overlapping_traces_df = get_non_overlapping_longest_duration_traces(traces_df)
    
    trace_durations: List[Dict[str, Any]] = []
    
    for _, row in non_overlapping_traces_df.iterrows():
        trace_id = row['trace_id']
        trace_start = row['start_time']
        trace_end = row['end_time']
        duration = row['duration']
        
        if duration <= 0:
            continue
            
        trace_durations.append({
            'trace_id': trace_id,
            'start_time': trace_start,
            'end_time': trace_end,
            'duration': duration
        })
    
    if not trace_durations:
        print("No valid traces found with positive duration.")
        return
        
    durations_df: pd.DataFrame = pd.DataFrame(trace_durations)
    median_duration: float = durations_df['duration'].median()
    print(f"Median trace duration: {median_duration} microseconds")
    
    normalized_perf_data: List[Dict[str, Any]] = []
    
    for trace_info in trace_durations:
        trace_id: str = trace_info['trace_id']
        trace_start: int = trace_info['start_time']
        trace_end: int = trace_info['end_time']
        trace_duration: int = trace_info['duration']
        
        # Get all timestamps from all cores within the trace window
        all_timestamps = set()
        for core_df in core_to_profile_data_df.values():
            core_df = core_df[
                (core_df['Time'] >= trace_start) & 
                (core_df['Time'] <= trace_end)
            ]
            all_timestamps.update(core_df['Time'].unique())
        
        all_timestamps = sorted(list(all_timestamps))
        
        # For each timestamp, sum up LLC loads and misses across all cores
        for timestamp in all_timestamps:
            total_llc_loads = 0
            total_llc_misses = 0
            
            for core_df in core_to_profile_data_df.values():
                core_df = core_df[
                    (core_df['Time'] >= trace_start) & 
                    (core_df['Time'] <= trace_end)
                ]
                if not core_df.empty:
                    timestamp_data = core_df[core_df['Time'] == timestamp]
                    if not timestamp_data.empty:
                        total_llc_loads += timestamp_data['LLC-loads'].iloc[0]
                        total_llc_misses += timestamp_data['LLC-misses'].iloc[0]
        
            # Get instructions for the core with highest instructions for this trace
            core_with_highest_instructions = None
            max_instructions = 0
            
            for core_id, core_df in core_to_profile_data_df.items():
                core_df = core_df[
                    (core_df['Time'] >= trace_start) & 
                    (core_df['Time'] <= trace_end)
                ]
                if not core_df.empty:
                    total_instructions = core_df['Instructions'].sum()
                    if total_instructions > max_instructions:
                        max_instructions = total_instructions
                        core_with_highest_instructions = core_id
            
            if core_with_highest_instructions is None:
                continue
                
            instructions_df = core_to_profile_data_df[core_with_highest_instructions]
            instructions_df = instructions_df[
                (instructions_df['Time'] >= trace_start) & 
                (instructions_df['Time'] <= trace_end)
            ]
            
            if instructions_df.empty:
                continue
                
            # Get instructions for this timestamp
            timestamp_instructions = instructions_df[instructions_df['Time'] == timestamp]['Instructions'].iloc[0] if not instructions_df[instructions_df['Time'] == timestamp].empty else 0
            
            # Normalize the data
            relative_position = (timestamp - trace_start) / trace_duration
            relative_position = max(0, min(1, relative_position))
            
            normalized_perf_data.append({
                'trace_id': trace_id,
                'absolute_time': timestamp,
                'relative_position': relative_position,
                'LLC-loads': total_llc_loads,
                'LLC-misses': total_llc_misses,
                'Instructions': timestamp_instructions,
                'core_id': core_with_highest_instructions
            })
    
    if not normalized_perf_data:
        print("No performance data found within trace windows.")
        return
        
    norm_df: pd.DataFrame = pd.DataFrame(normalized_perf_data)
    
    num_bins_in_microseconds: int = math.ceil(median_duration)
    
    bin_edges: np.ndarray = np.linspace(0, 1, num_bins_in_microseconds + 1)
    bin_centers: np.ndarray = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    binned_llc_loads: List[List[float]] = [[] for _ in range(num_bins_in_microseconds)]
    binned_llc_misses: List[List[float]] = [[] for _ in range(num_bins_in_microseconds)]
    binned_instructions: Dict[str, List[List[float]]] = {core_id: [[] for _ in range(num_bins_in_microseconds)] for core_id in core_to_profile_data_df.keys()}
    
    for _, row in norm_df.iterrows():
        bin_idx: int = min(int(row['relative_position'] * num_bins_in_microseconds), num_bins_in_microseconds - 1)
        binned_llc_loads[bin_idx].append(row['LLC-loads'])
        binned_llc_misses[bin_idx].append(row['LLC-misses'])
        binned_instructions[row['core_id']][bin_idx].append(row['Instructions'])
    
    median_llc_loads: List[float] = []
    median_llc_misses: List[float] = []
    median_instructions: Dict[str, List[float]] = {core_id: [] for core_id in core_to_profile_data_df.keys()}
    valid_bin_centers: List[float] = []
    
    for i in range(num_bins_in_microseconds):
        if binned_llc_loads[i] and binned_llc_misses[i]:
            median_llc_loads.append(np.median([x for x in binned_llc_loads[i] if x > 0]))
            median_llc_misses.append(np.median([x for x in binned_llc_misses[i] if x > 0]))
            valid_bin_centers.append(bin_centers[i])
            
            # Calculate median instructions for each core
            for core_id in core_to_profile_data_df.keys():
                if binned_instructions[core_id][i]:
                    median_instructions[core_id].append(np.median([x for x in binned_instructions[core_id][i] if x > 0]))
                else:
                    median_instructions[core_id].append(0)
    
    time_points: np.ndarray = np.array(valid_bin_centers) * median_duration
    
    fig: plt.Figure
    axs: List[plt.Axes]
    fig, axs = plt.subplots(2, 1, figsize=(15, 10))
    fig.suptitle(
        f"{container_name} | {service_name_for_traces} | {config}\n"
        f"Aligned Median Resource Usage (Median Duration: {median_duration:.2f} μs)",
        fontsize=14, fontweight='bold'
    )
    
    # Plot LLC Loads and LLC Misses together
    axs[0].scatter(time_points, median_llc_loads, s=10, alpha=0.7, color="blue", label="LLC Loads")
    axs[0].scatter(time_points, median_llc_misses, s=10, alpha=0.7, color="red", label="LLC Misses")
    axs[0].set_title("Median LLC Loads and LLC Misses (Summed Across Cores)")
    axs[0].set_ylabel("Count")
    axs[0].set_xlim(0, median_duration)
    axs[0].legend()
    
    # Plot Instructions for each core
    colors = plt.cm.Dark2(np.linspace(0, 1, len(median_instructions)))
    for (core_id, instructions), color in zip(median_instructions.items(), colors):
        axs[1].scatter(time_points, instructions, s=10, alpha=0.7, color=color, label=f"Core {core_id}")
    
    axs[1].set_title("Median Instructions per Core")
    axs[1].set_xlabel("Relative Time (μs)")
    axs[1].set_ylabel("Count")
    axs[1].set_xlim(0, median_duration)
    axs[1].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    plot_path: str = f"{output_dir}/aligned_median_resource_usage_plot_{config}.png"
    plt.savefig(plot_path, bbox_inches='tight')
    plt.close()
    
    print(f"Aligned median resource usage plot saved to {plot_path}")
    print(f"Number of traces analyzed: {len(durations_df)}")
    print(f"Number of bins with data: {len(valid_bin_centers)}")

def get_highest_resource_usage_traces(traces_df: pd.DataFrame, 
                                      core_to_profile_data_df: Dict[str, pd.DataFrame], 
                                      num_samples: int) -> pd.DataFrame:
    non_overlapping_traces_df = get_non_overlapping_longest_duration_traces(traces_df)
    
    trace_stats = []
    
    # get min and max perf time across all cores
    min_perf_time = min([df['Time'].min() for df in core_to_profile_data_df.values()])
    max_perf_time = max([df['Time'].max() for df in core_to_profile_data_df.values()])
    
    for _, row in non_overlapping_traces_df.iterrows():
        trace_id = row['trace_id']
        trace_start = row['start_time']
        trace_end = row['end_time']
        duration = row['duration']

        if trace_end < min_perf_time or trace_start > max_perf_time:
            continue
        if trace_start < min_perf_time or trace_end > max_perf_time:
            continue

        non_zero_llc_loads = 0
        non_zero_llc_misses = 0
        non_zero_instructions = 0

        curr_core_with_highest_instructions = None
        highest_instructions = 0
        core_to_instructions = {}
        core_to_llc_loads = {}
        core_to_llc_misses = {}

        for core_no, profile_data_df in core_to_profile_data_df.items():
            trace_perf_data = profile_data_df[
                (profile_data_df['Time'] >= trace_start) & 
                (profile_data_df['Time'] <= trace_end)
            ]

            if trace_perf_data.empty:
                continue

            instructions_count = (trace_perf_data['Instructions'] > 0).sum()
            llc_loads_count = (trace_perf_data['LLC-loads'] > 0).sum()
            llc_misses_count = (trace_perf_data['LLC-misses'] > 0).sum()

            core_to_instructions[core_no] = instructions_count
            core_to_llc_loads[core_no] = llc_loads_count
            core_to_llc_misses[core_no] = llc_misses_count

            non_zero_llc_loads += llc_loads_count
            non_zero_llc_misses += llc_misses_count
            non_zero_instructions += instructions_count

            if instructions_count > highest_instructions:
                highest_instructions = instructions_count
                curr_core_with_highest_instructions = core_no
        
        total_resource_usage = non_zero_llc_loads + non_zero_llc_misses + non_zero_instructions
        
        trace_stats.append({
            'trace_id': trace_id,
            'start_time': trace_start,
            'end_time': trace_end,
            'non_zero_llc_loads': non_zero_llc_loads,
            'non_zero_llc_misses': non_zero_llc_misses,
            'non_zero_instructions': non_zero_instructions,
            'total_resource_usage': total_resource_usage,
            'duration': duration,
            'core_with_highest_instructions': curr_core_with_highest_instructions,
            'core_to_instructions': core_to_instructions,
            'core_to_llc_loads': core_to_llc_loads,
            'core_to_llc_misses': core_to_llc_misses
        })
    
    trace_stats_df = pd.DataFrame(trace_stats)
    if trace_stats_df.empty:
        return pd.DataFrame()
    
    trace_stats_df = trace_stats_df.sort_values(by='total_resource_usage', ascending=False)
    
    top_traces = trace_stats_df.head(num_samples)
    
    print(f"Top {len(top_traces)} traces by resource usage:")
    for i, (_, row) in enumerate(top_traces.iterrows()):
        core_to_instructions_str = ""
        for core_no, instructions in row['core_to_instructions'].items():
                core_to_instructions_str += f"{core_no}: {instructions}, "

        core_to_llc_loads_str = ""
        for core_no, llc_loads in row['core_to_llc_loads'].items():
            core_to_llc_loads_str += f"{core_no}: {llc_loads}, "

        core_to_llc_misses_str = ""
        for core_no, llc_misses in row['core_to_llc_misses'].items():
            core_to_llc_misses_str += f"{core_no}: {llc_misses}, "

        print(f"  {i+1}. Trace ID: {row['trace_id']}, "
              f"Non-zero LLC loads: {row['non_zero_llc_loads']}, "
              f"Non-zero LLC misses: {row['non_zero_llc_misses']}, "
              f"Non-zero instructions: {row['non_zero_instructions']}, "
              f"Duration: {row['duration']}, "
              f"Total: {row['total_resource_usage']}, "
              f"Core with highest instructions: {row['core_with_highest_instructions']}, "
              f"Core to instructions: {core_to_instructions_str}, "
              f"Core to LLC loads: {core_to_llc_loads_str}, "
              f"Core to LLC misses: {core_to_llc_misses_str}")
    
    return top_traces 

def save_trace_profile_csvs(
    highest_resource_usage_traces: pd.DataFrame,
    cores_to_profile_data_df: Dict[str, pd.DataFrame],
    output_dir: str,
    container_name: str,
    config: str
) -> None:
    if highest_resource_usage_traces.empty:
        print("No traces found to save profile data.")
        return

    os.makedirs(output_dir, exist_ok=True)

    instructions_df = pd.DataFrame()
    llc_loads_df = pd.DataFrame()
    llc_misses_df = pd.DataFrame()

    for _, trace in highest_resource_usage_traces.iterrows():
        trace_id = trace["trace_id"]
        trace_start = trace["start_time"]
        trace_end = trace["end_time"]
        core_with_highest_instructions = trace["core_with_highest_instructions"]

        profile_df = cores_to_profile_data_df[core_with_highest_instructions]
        profile_df = profile_df[
            (profile_df["Time"] >= trace_start) & 
            (profile_df["Time"] <= trace_end)
        ].copy()

        if profile_df.empty:
            continue

        # Normalize timestamps
        profile_df["normalized_time"] = profile_df["Time"] - trace_start

        # Add instructions data from core with highest instructions
        instructions_df[f"trace_{trace_id}"] = profile_df.set_index("normalized_time")["Instructions"]

        # Sum up LLC loads and misses across all cores
        total_llc_loads = pd.Series(0, index=profile_df.index)
        total_llc_misses = pd.Series(0, index=profile_df.index)

        for core_id, core_df in cores_to_profile_data_df.items():
            core_df = core_df[
                (core_df["Time"] >= trace_start) & 
                (core_df["Time"] <= trace_end)
            ]
            if not core_df.empty:
                core_df = core_df.set_index("Time")
                total_llc_loads += core_df["LLC-loads"].reindex(profile_df["Time"]).fillna(0)
                total_llc_misses += core_df["LLC-misses"].reindex(profile_df["Time"]).fillna(0)

        llc_loads_df[f"trace_{trace_id}"] = total_llc_loads.set_index(profile_df["normalized_time"])
        llc_misses_df[f"trace_{trace_id}"] = total_llc_misses.set_index(profile_df["normalized_time"])

    instructions_df.to_csv(os.path.join(output_dir, f"traces_instructions_core_{core_with_highest_instructions}_{container_name}_{config}.csv"))
    llc_loads_df.to_csv(os.path.join(output_dir, f"traces_llc_loads_{container_name}_{config}.csv"))
    llc_misses_df.to_csv(os.path.join(output_dir, f"traces_llc_misses_{container_name}_{config}.csv"))

    print(f"Saved trace profile CSVs to {output_dir}") 

def plot_traces_start_end_times_and_perf_data(
    traces_df: pd.DataFrame,
    core_to_profile_data_df: Dict[str, pd.DataFrame],
    output_dir: str
) -> None:
    non_overlapping_traces_df = get_non_overlapping_longest_duration_traces(traces_df)

    num_cores = len(core_to_profile_data_df)
    fig, axs = plt.subplots(num_cores, 1, figsize=(15, 4*num_cores))
    fig.suptitle("Instructions per Core with Trace Start/End Times", fontsize=14, fontweight='bold')

    if num_cores == 1:
        axs = [axs]

    for i, (core_id, perf_df) in enumerate(core_to_profile_data_df.items()):
        ax = axs[i]
        
        ax.plot(perf_df['Time'], perf_df['Instructions'], label=f'Core {core_id} Instructions', color='blue', alpha=0.7)
        
        for _, trace in non_overlapping_traces_df.iterrows():
            trace_start = trace['start_time']
            trace_end = trace['end_time']
            trace_id = trace['trace_id']
            
            ax.axvline(x=trace_start, color='red', linestyle='--', alpha=0.5)
            ax.axvline(x=trace_end, color='red', linestyle='--', alpha=0.5)
            ax.axvspan(trace_start, trace_end, alpha=0.1, color='red', label=f'Trace {trace_id}')
        
        ax.set_title(f'Core {core_id} Instructions')
        ax.set_xlabel('Time (μs)')
        ax.set_ylabel('Instructions')
        ax.grid(True)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    
    plot_path = os.path.join(output_dir, 'traces_instructions_plot.png')
    plt.savefig(plot_path, bbox_inches='tight')
    plt.close()

    print(f"Plot saved to {plot_path}")

def plot_profile_with_traces(
    trace_stats_df: pd.DataFrame,
    cores_to_profile_data_df: Dict[str, pd.DataFrame],
    output_dir: str,
    num_samples: int,
    config: str,
    container_name: str,
    service_name_for_traces: str
) -> None:
    num_plots = 0

    print(f"Plotting top {min(num_samples, len(trace_stats_df))} traces by resource usage")

    for i, trace in trace_stats_df.iterrows():
        if num_plots == num_samples:
            break

        trace_id = trace["trace_id"]
        trace_start = trace["start_time"]
        trace_end = trace["end_time"]
        non_zero_llc_loads = trace["non_zero_llc_loads"]
        non_zero_llc_misses = trace["non_zero_llc_misses"]
        non_zero_instructions = trace["non_zero_instructions"]
        total_resource_usage = trace["total_resource_usage"]
        core_with_highest_instructions = trace["core_with_highest_instructions"]

        # Get performance data for the core with the highest instructions (assumption being the trace was executed on this core)
        profile_df = cores_to_profile_data_df[core_with_highest_instructions]
        profile_df["Time"] = profile_df["Time"].astype(int)

        plot_profile_df = profile_df[
            (profile_df["Time"] >= trace_start) & 
            (profile_df["Time"] <= trace_end)
        ]

        if plot_profile_df.empty:
            print(f"No performance data found for trace_id {trace_id}")
            continue

        zoom_margin = 0.01 * (trace_end - trace_start)
        zoomed_plot_profile_df = profile_df[
            (profile_df["Time"] >= trace_start - zoom_margin) &
            (profile_df["Time"] <= trace_end + zoom_margin)
        ]
        zoomed_plot_profile_df = zoomed_plot_profile_df.sort_values(by="Time")

        # make zoomed_plot_profile_df have a contimuous time index from min time to max time and fill the missing values with NaN
        zoomed_plot_profile_df = zoomed_plot_profile_df.set_index("Time")
        zoomed_plot_profile_df = zoomed_plot_profile_df.reindex(range(zoomed_plot_profile_df.index.min(), zoomed_plot_profile_df.index.max() + 1))
        zoomed_plot_profile_df = zoomed_plot_profile_df.reset_index()

        # Sum up LLC loads and misses across all cores for the trace time window
        total_llc_loads: pd.DataFrame = pd.DataFrame()
        total_llc_misses: pd.DataFrame = pd.DataFrame()
        for _, core_df in cores_to_profile_data_df.items():
            core_df = core_df[
                (core_df["Time"] >= trace_start - zoom_margin) &
                (core_df["Time"] <= trace_end + zoom_margin)
            ]
            if not core_df.empty:
                llc_loads = get_processed_df(core_df, "LLC-loads", False)
                llc_misses = get_processed_df(core_df, "LLC-misses", False)
                total_llc_loads = pd.concat([total_llc_loads, llc_loads], axis=0)
                total_llc_misses = pd.concat([total_llc_misses, llc_misses], axis=0)
        total_llc_loads = total_llc_loads.groupby("Time").sum()
        total_llc_misses = total_llc_misses.groupby("Time").sum()

        # make sure the total_llc_loads and total_llc_misses have a continuous time index from min time of zoomed_plot_profile_df to max time of zoomed_plot_profile_df
        total_llc_loads = total_llc_loads.reindex(zoomed_plot_profile_df["Time"])
        total_llc_misses = total_llc_misses.reindex(zoomed_plot_profile_df["Time"])
        
        if len(total_llc_loads) != len(zoomed_plot_profile_df) or len(total_llc_misses) != len(zoomed_plot_profile_df):
            print(f"Trace {trace_id} has unequal lengths for LLC loads/misses and profile data. Lengths: zoomed_profile_df={len(zoomed_plot_profile_df)}, LLC loads={len(total_llc_loads)}, LLC misses={len(total_llc_misses)}")

        total_llc_loads_series = total_llc_loads["LLC-loads"]
        total_llc_misses_series = total_llc_misses["LLC-misses"]

        # Set the summed values back to the DataFrame
        zoomed_plot_profile_df["LLC-loads"] = total_llc_loads_series.values
        zoomed_plot_profile_df["LLC-misses"] = total_llc_misses_series.values

        # Replace zeros with NaN for better visualization
        zoomed_plot_profile_df["LLC-loads"] = zoomed_plot_profile_df["LLC-loads"].replace(0, np.nan)
        zoomed_plot_profile_df["LLC-misses"] = zoomed_plot_profile_df["LLC-misses"].replace(0, np.nan)
        zoomed_plot_profile_df["Instructions"] = zoomed_plot_profile_df["Instructions"].replace(0, np.nan)

        cache_partitions_str = ""
        config_parts = config.split("_")
        for part in config_parts:
            if part.startswith("cp"):
                cache_partitions_str = part
                break

        fig, axs = plt.subplots(2, 1, figsize=(15, 10))
        fig.suptitle(
            f"{container_name} | {service_name_for_traces} | {cache_partitions_str}\n"
            f"Trace ID: {trace_id} | Resource Usage: LLC-loads={non_zero_llc_loads}, "
            f"LLC-misses={non_zero_llc_misses}, Instructions={non_zero_instructions}", 
            fontsize=14, fontweight='bold'
        )

        axs[0].scatter(zoomed_plot_profile_df["Time"], zoomed_plot_profile_df['LLC-loads'], s=10, alpha=0.7, color="blue", label="LLC Loads")
        axs[0].scatter(zoomed_plot_profile_df["Time"], zoomed_plot_profile_df['LLC-misses'], s=10, alpha=0.7, color="red", label="LLC Misses")
        axs[0].axvspan(trace_start, trace_end, alpha=0.2, color=(1, 0.7, 0.7), label="Trace Window")
        axs[0].set_title("LLC Loads and LLC Misses (Zoomed In)")
        axs[0].set_xlabel("Time (microseconds)")
        axs[0].set_ylabel("Count")
        axs[0].legend()

        axs[1].scatter(zoomed_plot_profile_df["Time"], zoomed_plot_profile_df['Instructions'], s=10, alpha=0.7, color="green", label="Instructions")
        axs[1].axvspan(trace_start, trace_end, alpha=0.2, color=(1, 0.7, 0.7), label="Trace Window")
        axs[1].set_title("Instructions from Core {core_with_highest_instructions} (Zoomed In)")
        axs[1].set_xlabel("Time (microseconds)")
        axs[1].set_ylabel("Instruction (Delta) Count")
        axs[1].legend()

        plt.tight_layout()
        plt.savefig(f"{output_dir}/trace_{num_plots+1}_{config}_zoomed_perf_plot.png")
        plt.close()

        num_plots += 1

        print(f"Plot {num_plots} saved: trace_id={trace_id}, resource_usage={total_resource_usage}") 

def main() -> None:
    global DEFAULT_SERVICE_NAME

    args: argparse.Namespace = parse_arguments()
    test_name: str = args.test_name.replace(" ", "_")
    service_name_for_traces: str = args.service_name_for_traces
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    profile_data_dir: str = args.profile_data_dir
    traces_data_dir: str = args.trace_data_dir
    samples: int = args.samples
    plot_dir: str = args.plot_dir
    save_trace_profile_csvs: bool = args.save_trace_profile_csvs
    trace_profile_csv_dir: str = args.trace_profile_csv_dir
    
    if args.default_service_name:
        DEFAULT_SERVICE_NAME = args.default_service_name

    print("Running with the following arguments:")
    print(f"Test name: {test_name}")
    print(f"Container name: {container_name}")
    print(f"Service name for traces: {service_name_for_traces}")
    print(f"Samples per operation: {samples}")
    print(f"Configuration: {config}")
    print(f"Profile data directory: {profile_data_dir}")
    print(f"Traces data directory: {traces_data_dir}")
    print(f"Plot directory: {plot_dir}")
    print(f"Save trace profile CSVs: {save_trace_profile_csvs}")
    print(f"Trace profile CSV directory: {trace_profile_csv_dir}")
    print(f"Default service name: {DEFAULT_SERVICE_NAME}")
    
    container_jaeger_traces_df: pd.DataFrame = load_traces_data(
        traces_data_dir, service_name_for_traces, test_name, config, container_name)
    cores_to_profile_data_df: pd.DataFrame = load_profile_data(profile_data_dir)

    if container_jaeger_traces_df.empty:
        print(f"No traces found for container [{container_name}] with service name [{service_name_for_traces}]")
        return
    if len(cores_to_profile_data_df) == 0:
        print(f"No performance data found for container [{container_name}]")
        return
    
    print("Container Jaeger Traces Data:")
    print(container_jaeger_traces_df.head())
    print("Cores to Profile Data:")
    for core_id, core_df in cores_to_profile_data_df.items():
        print(f"Core {core_id} Profile Data:")
        print(core_df.head())
    
    # Get non-overlapping spans for time range reporting
    non_overlapping_traces_df = get_non_overlapping_longest_duration_traces(container_jaeger_traces_df)
    
    if not non_overlapping_traces_df.empty:
        edt = ZoneInfo("America/New_York")
        min_perf_time = min([df['Time'].min() for df in cores_to_profile_data_df.values()])
        max_perf_time = max([df['Time'].max() for df in cores_to_profile_data_df.values()])

        min_trace_time = non_overlapping_traces_df['start_time'].min()
        max_trace_time = non_overlapping_traces_df['end_time'].max()
        min_perf_time_dt = datetime.fromtimestamp(min_perf_time / 1e6, tz=timezone.utc).astimezone(edt)
        max_perf_time_dt = datetime.fromtimestamp(max_perf_time / 1e6, tz=timezone.utc).astimezone(edt)
        min_trace_time_dt = datetime.fromtimestamp(min_trace_time / 1e6, tz=timezone.utc).astimezone(edt)
        max_trace_time_dt = datetime.fromtimestamp(max_trace_time / 1e6, tz=timezone.utc).astimezone(edt)
        print(f"Performance data time range [{min_perf_time_dt} - {max_perf_time_dt}] aka [{min_perf_time} - {max_perf_time}]")
        print(f"Trace data time range [{min_trace_time_dt} - {max_trace_time_dt}] aka [{min_trace_time} - {max_trace_time}]")
    else:
        print("No valid non-overlapping traces found.")

    print("Plotting aligned median resource usage...")
    plot_aligned_median_resource_usage(
        container_jaeger_traces_df,
        cores_to_profile_data_df,
        plot_dir,
        config,
        container_name,
        service_name_for_traces
    )

    print("Plotting traces start/end times and performance data...")
    plot_traces_start_end_times_and_perf_data(
        container_jaeger_traces_df,
        cores_to_profile_data_df,
        plot_dir
    )

    print("Getting highest resource usage traces...")
    highest_resource_usage_traces = get_highest_resource_usage_traces(
        container_jaeger_traces_df,
        cores_to_profile_data_df,
        samples
    )
    if highest_resource_usage_traces.empty:
        print("No traces found with performance data.")
        return

    print("Plotting profile for highest resource usage traces...")
    plot_profile_with_traces(
        highest_resource_usage_traces, 
        cores_to_profile_data_df, 
        plot_dir, 
        samples, 
        config, 
        container_name, 
        service_name_for_traces
    )

    if save_trace_profile_csvs:
        if trace_profile_csv_dir:
            print("Saving trace profile CSVs...")
            save_trace_profile_csvs(
                highest_resource_usage_traces,
                cores_to_profile_data_df,
                args.trace_profile_csv_dir,
                container_name,
                config
            )
        else:
            print("Output directory for Trace-Profile CSV data not provided. Skipping CSV data saving.")
    
    print("Plot generation complete.")

if __name__ == "__main__":
    main()