import argparse
import os
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List
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

def plot_aligned_median_resource_usage(
    traces_df: pd.DataFrame, 
    profile_df: pd.DataFrame, 
    output_dir: str, 
    config: str, 
    container_name: str, 
    service_name_for_traces: str
) -> None:
    trace_durations: List[Dict[str, Any]] = []
    
    for trace_id in traces_df['trace_id'].unique():
        trace_data: pd.DataFrame = traces_df[traces_df['trace_id'] == trace_id]
        trace_start: int = trace_data['start_time'].min()
        trace_end: int = trace_data['end_time'].max()
        duration: int = trace_end - trace_start
        
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
    trace_stats = []
    trace_ids = list(traces_df['trace_id'].unique())
    
    min_perf_time = profile_df['Time'].min()
    max_perf_time = profile_df['Time'].max()
    
    for trace_id in trace_ids:
        trace_sample = traces_df[traces_df['trace_id'] == trace_id]
        trace_start = trace_sample['start_time'].min()
        trace_end = trace_sample['end_time'].max()
        duration = trace_sample['duration'].max()

        max_duration_row = trace_sample.loc[trace_sample['duration'].idxmax()]
        trace_start_max_duration = max_duration_row['start_time']
        trace_end_max_duration = max_duration_row['end_time']

        if trace_start != trace_start_max_duration or trace_end != trace_end_max_duration:
            print(f"WARNING: Trace ID {trace_id} has inconsistent start/end times. Trace start: {trace_start}, end: {trace_end}, max duration start: {trace_start_max_duration}, end: {trace_end_max_duration}, duration: {duration}")
        
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
    
    selected_traces = pd.DataFrame()
    for trace_id in top_traces['trace_id']:
        trace_data = traces_df[traces_df['trace_id'] == trace_id]
        selected_traces = pd.concat([selected_traces, trace_data])
    
    return selected_traces

def get_transformed_traces_df(traces_df: pd.DataFrame) -> pd.DataFrame:
    transformed_traces_df = traces_df.groupby(['trace_id']).agg(
        start_time=('start_time', 'min'),
        end_time=('end_time', 'max'),
        container_name=('container_name', 'first')
    ).reset_index()
    return transformed_traces_df

def plot_profile_with_traces(
    transformed_traces_df: pd.DataFrame,
    profile_df: pd.DataFrame,
    output_dir: str,
    num_samples: int,
    config: str,
    container_name: str,
    service_name_for_traces: str
) -> None:
    profile_df["Time"] = profile_df["Time"].astype(float)
    transformed_traces_df["start_time"] = transformed_traces_df["start_time"].astype(float)
    transformed_traces_df["end_time"] = transformed_traces_df["end_time"].astype(float)
    num_plots = 0

    print(f"Plotting top {min(num_samples, len(transformed_traces_df))} traces by resource usage")

    for i, trace in transformed_traces_df.iterrows():
        if num_plots == num_samples:
            break

        trace_start = trace["start_time"]
        trace_end = trace["end_time"]

        plot_profile_df = profile_df[
            (profile_df["Time"] >= trace_start) & 
            (profile_df["Time"] <= trace_end)
        ]

        if plot_profile_df.empty:
            print(f"No performance data found for trace_id {trace['trace_id']}")
            continue

        # Calculate resource usage stats for this trace
        non_zero_llc_loads = (plot_profile_df['LLC-loads'] > 0).sum()
        non_zero_llc_misses = (plot_profile_df['LLC-misses'] > 0).sum()
        non_zero_instructions = (plot_profile_df['Instructions'] > 0).sum()
        total_resource_usage = non_zero_llc_loads + non_zero_llc_misses + non_zero_instructions

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
            f"Trace ID: {trace['trace_id']} | Resource Usage: LLC-loads={non_zero_llc_loads}, "
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

        print(f"Plot {num_plots} saved: trace_id={trace['trace_id']}, resource_usage={total_resource_usage}")

def plot_traces_start_end_times_and_perf_data(
    container_traces_df: pd.DataFrame,
    profile_df: pd.DataFrame,
    output_dir: str
) -> None:
    delta = 0.0001
    threshold = 0.001

    plt.figure(figsize=(15, 5))
    transformed_traces_df = get_transformed_traces_df(container_traces_df)
    
    plt.scatter(profile_df["Time"], profile_df["Instructions"], s=10, alpha=0.7, label="Instructions")

    min_perf_time = profile_df['Time'].min()
    max_perf_time = profile_df['Time'].max()
    min_trace_time = transformed_traces_df['start_time'].min()
    max_trace_time = transformed_traces_df['end_time'].max()
    if min_trace_time < min_perf_time:
        min_perf_time = min_trace_time
    if max_trace_time > max_perf_time:
        max_perf_time = max_trace_time

    plt.xlim(min_perf_time, max_perf_time)
    
    for _, trace in transformed_traces_df.iterrows():
        start_time = trace["start_time"]
        end_time = trace["end_time"]

        if abs(end_time - start_time) < threshold:
            end_time += delta  

        plt.axvline(start_time, color='red', linestyle='--', label="Trace Start")
        plt.axvline(end_time, color='blue', linestyle=':', label="Trace End")
    
    plt.title("Trace Start (red --) / End (blue :) Times and Instructions (green)")
    plt.xlabel("Time (microseconds)")
    plt.ylabel("Count")
    plt.savefig(f"{output_dir}/traces_instructions_plot.png")
    plt.close()

    print(f"Plot saved to {output_dir}/traces_instructions_plot.png")

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
    min_trace_time = container_jaeger_traces_df['start_time'].min()
    max_trace_time = container_jaeger_traces_df['end_time'].max()
    min_perf_time_dt = datetime.fromtimestamp(min_perf_time / 1e6, tz=timezone.utc).astimezone(edt)
    max_perf_time_dt = datetime.fromtimestamp(max_perf_time / 1e6, tz=timezone.utc).astimezone(edt)
    min_trace_time_dt = datetime.fromtimestamp(min_trace_time / 1e6, tz=timezone.utc).astimezone(edt)
    max_trace_time_dt = datetime.fromtimestamp(max_trace_time / 1e6, tz=timezone.utc).astimezone(edt)
    print(f"Performance data time range [{min_perf_time_dt} - {max_perf_time_dt}] aka [{min_perf_time} - {max_perf_time}]")
    print(f"Trace data time range [{min_trace_time_dt} - {max_trace_time_dt}] aka [{min_trace_time} - {max_trace_time}]")

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

    transformed_traces_df = get_transformed_traces_df(highest_resource_usage_traces)
    plot_profile_with_traces(transformed_traces_df, profile_df, plot_dir, samples, config, container_name, service_name_for_traces)
    
    print("Plot generation complete.")

if __name__ == "__main__":
    main()
