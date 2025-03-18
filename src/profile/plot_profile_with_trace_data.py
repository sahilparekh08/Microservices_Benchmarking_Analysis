import argparse
import os
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List, Tuple
import math

DEFAULT_SERVICE_NAME = "nginx-web-server"

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Jaeger trace data for a given service.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Test configuration")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--samples", type=int, default=10, help="Number of samples per operation")
    parser.add_argument("--plot-dir", type=str, default="outputs", help="Output directory for plots")
    parser.add_argument("--default-service-name", type=str, help="Default service name for traces")

    return parser.parse_args()

def load_traces_data(
    data_dir: str,
    service_name_for_traces: str,
    test_name: str,
    config: str,
    container_name: str
) -> pd.DataFrame:
    global DEFAULT_SERVICE_NAME

    jaeger_traces_csv_file_path: str = os.path.join(data_dir, "data", 
                                                    f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    if not os.path.exists(jaeger_traces_csv_file_path):
        jaeger_traces_csv_file_path: str = os.path.join(data_dir, "data", 
                                                    f"{DEFAULT_SERVICE_NAME}_{test_name}_{config}_traces_data.csv")

    jaeger_traces_df: pd.DataFrame = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df: pd.DataFrame = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    return container_jaeger_traces_df

def load_perf_data(data_dir: str) -> pd.DataFrame:
    llc_data_file: str = f"{data_dir}/data/profile_data.csv"
    df: pd.DataFrame = pd.read_csv(llc_data_file, sep=",")
    return df

def get_non_overlapping_longest_durations(traces_df: pd.DataFrame) -> pd.DataFrame:
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
    profile_df: pd.DataFrame, 
    output_dir: str, 
    config: str, 
    container_name: str, 
    service_name_for_traces: str
) -> None:
    non_overlapping_traces_df = get_non_overlapping_longest_durations(traces_df)
    
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
        
        trace_perf_data: pd.DataFrame = profile_df[
            (profile_df['Time'] >= trace_start) & 
            (profile_df['Time'] <= trace_end)
        ]
        
        if trace_perf_data.empty:
            continue
            
        for _, row in trace_perf_data.iterrows():
            absolute_time: float = row['Time']
            relative_position: float = (absolute_time - trace_start) / trace_duration
            
            relative_position = max(0, min(1, relative_position))
            
            normalized_perf_data.append({
                'trace_id': trace_id,
                'absolute_time': absolute_time,
                'relative_position': relative_position,
                'LLC-loads': row['LLC-loads'],
                'LLC-misses': row['LLC-misses'],
                'Instructions': row['Instructions']
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
    binned_instructions: List[List[float]] = [[] for _ in range(num_bins_in_microseconds)]
    
    for _, row in norm_df.iterrows():
        bin_idx: int = min(int(row['relative_position'] * num_bins_in_microseconds), num_bins_in_microseconds - 1)
        binned_llc_loads[bin_idx].append(row['LLC-loads'])
        binned_llc_misses[bin_idx].append(row['LLC-misses'])
        binned_instructions[bin_idx].append(row['Instructions'])
    
    median_llc_loads: List[float] = []
    median_llc_misses: List[float] = []
    median_instructions: List[float] = []
    valid_bin_centers: List[float] = []
    
    for i in range(num_bins_in_microseconds):
        if binned_llc_loads[i] and binned_llc_misses[i] and binned_instructions[i]:
            median_llc_loads.append(np.median([x for x in binned_llc_loads[i] if x > 0]))
            median_llc_misses.append(np.median([x for x in binned_llc_misses[i] if x > 0]))
            median_instructions.append(np.median([x for x in binned_instructions[i] if x > 0]))
            valid_bin_centers.append(bin_centers[i])
    
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
    axs[0].set_title("Median LLC Loads and LLC Misses")
    axs[0].set_ylabel("Count")
    axs[0].set_xlim(0, median_duration)
    axs[0].legend()
    
    # Plot Instructions
    axs[1].scatter(time_points, median_instructions, s=10, alpha=0.7, color="green", label="Instructions")
    axs[1].set_title("Median Instructions")
    axs[1].set_xlabel("Relative Time (μs)")
    axs[1].set_ylabel("Count")
    axs[1].set_xlim(0, median_duration)
    axs[1].legend()
    
    plt.tight_layout()
    plot_path: str = f"{output_dir}/aligned_median_resource_usage_plot_{config}.png"
    plt.savefig(plot_path)
    plt.close()
    
    print(f"Aligned median resource usage plot saved to {plot_path}")
    print(f"Number of traces analyzed: {len(durations_df)}")
    print(f"Number of bins with data: {len(valid_bin_centers)}")

def get_highest_resource_usage_traces(traces_df: pd.DataFrame, profile_df: pd.DataFrame, num_samples: int) -> pd.DataFrame:
    # Get non-overlapping spans with largest durations for each trace
    non_overlapping_traces_df = get_non_overlapping_longest_durations(traces_df)
    
    trace_stats = []
    
    min_perf_time = profile_df['Time'].min()
    max_perf_time = profile_df['Time'].max()
    
    for _, row in non_overlapping_traces_df.iterrows():
        trace_id = row['trace_id']
        trace_start = row['start_time']
        trace_end = row['end_time']
        duration = row['duration']

        if trace_end < min_perf_time or trace_start > max_perf_time:
            continue
        if trace_start < min_perf_time or trace_end > max_perf_time:
            continue
        
        trace_perf_data = profile_df[
            (profile_df['Time'] >= trace_start) & 
            (profile_df['Time'] <= trace_end)
        ]
        
        if trace_perf_data.empty:
            continue
        
        non_zero_llc_loads = (trace_perf_data['LLC-loads'] > 0).sum()
        non_zero_llc_misses = (trace_perf_data['LLC-misses'] > 0).sum()
        non_zero_instructions = (trace_perf_data['Instructions'] > 0).sum()
        
        total_resource_usage = non_zero_llc_loads + non_zero_llc_misses + non_zero_instructions
        
        trace_stats.append({
            'trace_id': trace_id,
            'start_time': trace_start,
            'end_time': trace_end,
            'non_zero_llc_loads': non_zero_llc_loads,
            'non_zero_llc_misses': non_zero_llc_misses,
            'non_zero_instructions': non_zero_instructions,
            'total_resource_usage': total_resource_usage,
            'duration': duration
        })
    
    trace_stats_df = pd.DataFrame(trace_stats)
    if trace_stats_df.empty:
        return pd.DataFrame()
    
    trace_stats_df = trace_stats_df.sort_values(by='total_resource_usage', ascending=False)
    
    top_traces = trace_stats_df.head(num_samples)
    
    print(f"Top {len(top_traces)} traces by resource usage:")
    for i, (_, row) in enumerate(top_traces.iterrows()):
        print(f"  {i+1}. Trace ID: {row['trace_id']}, "
              f"Non-zero LLC loads: {row['non_zero_llc_loads']}, "
              f"Non-zero LLC misses: {row['non_zero_llc_misses']}, "
              f"Non-zero instructions: {row['non_zero_instructions']}, "
              f"Duration: {row['duration']}, "
              f"Total: {row['total_resource_usage']}")
    
    # Just return the top traces stats dataframe directly, since we already have all the info we need
    return top_traces

def plot_traces_start_end_times_and_perf_data(
    traces_df: pd.DataFrame,
    profile_df: pd.DataFrame,
    output_dir: str
) -> None:
    delta = 0.0001
    threshold = 0.001

    # Get non-overlapping spans with largest durations for each trace
    non_overlapping_traces_df = get_non_overlapping_longest_durations(traces_df)

    plt.figure(figsize=(15, 5))
    plt.scatter(profile_df["Time"], profile_df["Instructions"], s=10, alpha=0.7, label="Instructions")

    min_perf_time = profile_df['Time'].min()
    max_perf_time = profile_df['Time'].max()
    
    if not non_overlapping_traces_df.empty:
        min_trace_time = non_overlapping_traces_df['start_time'].min()
        max_trace_time = non_overlapping_traces_df['end_time'].max()
        if min_trace_time < min_perf_time:
            min_perf_time = min_trace_time
        if max_trace_time > max_perf_time:
            max_perf_time = max_trace_time

    plt.xlim(min_perf_time, max_perf_time)
    
    # Use a set to avoid duplicate labels in the legend
    start_label_used = False
    end_label_used = False
    
    for _, trace in non_overlapping_traces_df.iterrows():
        start_time = trace["start_time"]
        end_time = trace["end_time"]

        if abs(end_time - start_time) < threshold:
            end_time += delta  

        start_label = "Trace Start" if not start_label_used else ""
        end_label = "Trace End" if not end_label_used else ""
        
        plt.axvline(start_time, color='red', linestyle='--', label=start_label)
        plt.axvline(end_time, color='blue', linestyle=':', label=end_label)
        
        start_label_used = True
        end_label_used = True
    
    plt.title("Trace Start (red --) / End (blue :) Times and Instructions (green)")
    plt.xlabel("Time (microseconds)")
    plt.ylabel("Count")
    
    # Remove duplicate labels
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())
    
    plt.savefig(f"{output_dir}/traces_instructions_plot.png")
    plt.close()

    print(f"Plot saved to {output_dir}/traces_instructions_plot.png")

def plot_profile_with_traces(
    trace_stats_df: pd.DataFrame,
    profile_df: pd.DataFrame,
    output_dir: str,
    num_samples: int,
    config: str,
    container_name: str,
    service_name_for_traces: str
) -> None:
    profile_df["Time"] = profile_df["Time"].astype(float)
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

        zoomed_plot_profile_df["LLC-loads"] = zoomed_plot_profile_df["LLC-loads"].astype(int)
        zoomed_plot_profile_df["LLC-misses"] = zoomed_plot_profile_df["LLC-misses"].astype(int)
        zoomed_plot_profile_df["Instructions"] = zoomed_plot_profile_df["Instructions"].astype(int)

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
        axs[1].set_title("Instructions (Zoomed In)")
        axs[1].set_xlabel("Time (microseconds)")
        axs[1].set_ylabel("Count")
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
    data_dir: str = args.data_dir
    samples: int = args.samples
    plot_dir: str = args.plot_dir
    
    if args.default_service_name:
        DEFAULT_SERVICE_NAME = args.default_service_name

    print(f"Loading data from {data_dir} for test {test_name} with config {config}")
    print(f"Container name: {container_name}")
    print(f"Service name for traces: {service_name_for_traces}")
    print(f"Samples per operation: {samples}")
    print(f"Plot directory: {plot_dir}")
    print(f"Default service name: {DEFAULT_SERVICE_NAME}")
    
    container_jaeger_traces_df: pd.DataFrame = load_traces_data(
        data_dir, service_name_for_traces, test_name, config, container_name)
    profile_df: pd.DataFrame = load_perf_data(data_dir)

    if container_jaeger_traces_df.empty:
        print(f"No traces found for container [{container_name}] with service name [{service_name_for_traces}]")
        return
    if profile_df.empty:
        print(f"No performance data found for container [{container_name}]")
        return

    edt = ZoneInfo("America/New_York")
    min_perf_time = profile_df['Time'].min()
    max_perf_time = profile_df['Time'].max()
    
    # Get non-overlapping spans for time range reporting
    non_overlapping_traces_df = get_non_overlapping_longest_durations(container_jaeger_traces_df)
    
    if not non_overlapping_traces_df.empty:
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

    plot_aligned_median_resource_usage(
        container_jaeger_traces_df,
        profile_df,
        plot_dir,
        config,
        container_name,
        service_name_for_traces
    )

    plot_traces_start_end_times_and_perf_data(
        container_jaeger_traces_df,
        profile_df,
        plot_dir
    )

    highest_resource_usage_traces = get_highest_resource_usage_traces(
        container_jaeger_traces_df,
        profile_df,
        samples
    )
    if highest_resource_usage_traces.empty:
        print("No traces found with performance data.")
        return

    plot_profile_with_traces(
        highest_resource_usage_traces, 
        profile_df, 
        plot_dir, 
        samples, 
        config, 
        container_name, 
        service_name_for_traces
    )
    
    print("Plot generation complete.")

if __name__ == "__main__":
    main()