import argparse
import os
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List, Tuple
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
    parser.add_argument("--samples", type=int, default=5, help="Number of samples per operation")
    parser.add_argument("--plot-dir", type=str, default="outputs", help="Output directory for plots")
    parser.add_argument("--default-service-name", type=str, help="Default service name for traces")
    parser.add_argument("--save-trace-profile-csvs", type=bool, default=False, help="Save trace profile CSVs")
    parser.add_argument("--trace-profile-csv-dir", type=str, help="Output directory for CSV data")
    parser.add_argument("--save-median-resource-usage-csvs", type=bool, default=False, help="Save median plot CSVs")

    return parser.parse_args()

def load_traces_data(
    data_dir: str,
    service_name_for_traces: str,
    test_name: str,
    config: str,
    container_name: str
) -> pd.DataFrame:
    global DEFAULT_SERVICE_NAME

    jaeger_traces_csv_file_path: str = os.path.join(data_dir, f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    if not os.path.exists(jaeger_traces_csv_file_path):
        print(f"File not found: {jaeger_traces_csv_file_path}, trying default service name: {DEFAULT_SERVICE_NAME}")
        jaeger_traces_csv_file_path: str = os.path.join(data_dir, f"{DEFAULT_SERVICE_NAME}_{test_name}_{config}_traces_data.csv")

    jaeger_traces_df: pd.DataFrame = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df: pd.DataFrame = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    return container_jaeger_traces_df

def get_trace_id_to_non_idle_intervals(traces_df: pd.DataFrame) -> Dict[str, List[Dict[int, int]]]:
    trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]] = {}
    for _, row in traces_df.iterrows():
        trace_id = row['trace_id']
        non_idle_intervals = row['non_idle_intervals'].split(";")
        for interval in non_idle_intervals:
            start, end = map(int, interval.split("-"))
            if trace_id not in trace_id_to_non_idle_intervals:
                trace_id_to_non_idle_intervals[trace_id] = []
            trace_id_to_non_idle_intervals[trace_id].append({start: end})
    if not trace_id_to_non_idle_intervals:
        print("No non idle intervals found in the trace data.")
        return {}
    
    for trace_id, intervals in trace_id_to_non_idle_intervals.items():
        sorted_intervals = sorted(intervals, key=lambda x: list(x.keys())[0])
        trace_id_to_non_idle_intervals[trace_id] = sorted_intervals

    # merge intervals for each trace id
    for trace_id, intervals in trace_id_to_non_idle_intervals.items():
        merged_intervals = []
        current_start, current_end = None, None
        for interval in intervals:
            for start, end in interval.items():
                if current_start is None:
                    current_start, current_end = start, end
                elif start <= current_end:
                    current_end = max(current_end, end)
                else:
                    merged_intervals.append({current_start: current_end})
                    current_start, current_end = start, end
        if current_start is not None:
            merged_intervals.append({current_start: current_end})
        trace_id_to_non_idle_intervals[trace_id] = merged_intervals

    return trace_id_to_non_idle_intervals

def get_median_non_idle_intervals(trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]]) -> int:
    # Calculate median number of non idle intervals across all traces
    non_idle_intervals_lens: List[int] = []
    for trace_id, non_idle_intervals in trace_id_to_non_idle_intervals.items():
        non_idle_intervals_lens.append(len(non_idle_intervals))
    if not non_idle_intervals_lens:
        print("No non idle intervals found for any traces.")
        return
    len_non_idle_intervals_to_count_map: Dict[int, int] = {}
    for length in non_idle_intervals_lens:
        if length not in len_non_idle_intervals_to_count_map:
            len_non_idle_intervals_to_count_map[length] = 0
        len_non_idle_intervals_to_count_map[length] += 1
    if len_non_idle_intervals_to_count_map:
        print(f"Non idle intervals length distribution: {len_non_idle_intervals_to_count_map}")
    non_idle_intervals_lens = sorted(non_idle_intervals_lens)
    median_non_idle_intervals: int = int(np.median(non_idle_intervals_lens))
    print(f"Median number of non idle intervals: {median_non_idle_intervals}")

    return median_non_idle_intervals

def get_median_duration_information_for_non_idle_intervals(
        trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]],
        median_non_idle_intervals: int
) -> Tuple[Dict[int, int], Dict[int, Dict[str, int]]]:
    # calculate the median duration for each non idle interval
    median_duration_per_non_idle_interval: Dict[int, int] = {}
    non_idle_duration_index_to_trace_id_non_idle_duration_map: Dict[int, Dict[str, int]] = {}
    for i in range(median_non_idle_intervals):
        non_idle_duration_index_to_trace_id_non_idle_duration_map[i] = {}
    for i in range(median_non_idle_intervals):
        durations: List[int] = []
        for trace_id, non_idle_intervals in trace_id_to_non_idle_intervals.items():
            non_idle_interval: Dict[int, int] = non_idle_intervals[i]
            start, end = list(non_idle_interval.items())[0]
            duration = end - start
            non_idle_duration_index_to_trace_id_non_idle_duration_map[i][trace_id] = duration
            durations.append(duration)
        median_duration_per_non_idle_interval[i] = int(np.median(durations))

    return median_duration_per_non_idle_interval, non_idle_duration_index_to_trace_id_non_idle_duration_map

def get_selected_traces_based_non_median_non_idle_intervals(
        median_duration_per_non_idle_interval: Dict[int, int],
        non_idle_duration_index_to_trace_id_non_idle_duration_map: Dict[int, Dict[str, int]],
        median_non_idle_intervals: int
) -> set[str]:
    # select traces whose duration lies in median +- 1 sd for each non idle interval
    non_idle_interval_index_to_trace_ids: Dict[int, List[str]] = {}
    for i in range(median_non_idle_intervals):
        median_duration: int = median_duration_per_non_idle_interval[i]
        sd_duration: float = np.std(list(non_idle_duration_index_to_trace_id_non_idle_duration_map[i].values()))
        lower_bound: int = int(median_duration - (sd_duration))
        upper_bound: int = int(median_duration + (sd_duration))
        trace_ids_list: List[str] = []
        for trace_id, duration in non_idle_duration_index_to_trace_id_non_idle_duration_map[i].items():
            if lower_bound <= duration <= upper_bound:
                trace_ids_list.append(trace_id)
        non_idle_interval_index_to_trace_ids[i] = trace_ids_list
    # take an intersection of trace ids from the set of selected traces across all non idle intervals
    selected_trace_ids: set[str] = []
    for i in range(median_non_idle_intervals):
        if i == 0:
            selected_trace_ids = set(non_idle_interval_index_to_trace_ids[i])
        else:
            selected_trace_ids = selected_trace_ids.intersection(set(non_idle_interval_index_to_trace_ids[i]))
    if not selected_trace_ids:
        print("No traces found that match the median duration +- 1 standard deviation criteria across all non idle intervals.")
        return
    
    return selected_trace_ids

def plot_aligned_median_resource_usage(
    trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]],
    median_non_idle_intervals: int,
    median_duration_per_non_idle_interval: Dict[int, int],
    core_to_profile_data_df: Dict[str, pd.DataFrame],
    profile_data_dir: str,
    output_dir: str, 
    config: str, 
    container_name: str,
    save_median_resource_usage_csvs: bool
) -> None:
    print(f"Plotting aligned median resource usage for traces in {container_name} with config {config}")
    
    # process perf data
    normalised_perf_data_per_non_idle_interval: Dict[int, # non idle interval index
                                                        List[ #records for each timestamp
                                                            Dict[str, Any]
                                                            ]
                                                        ] = {}
    for i in range(median_non_idle_intervals):
        normalised_perf_data_per_non_idle_interval[i] = []
    for trace_id, non_idle_intervals in trace_id_to_non_idle_intervals.items():
        for i, non_idle_interval in enumerate(non_idle_intervals):
            non_idle_interval_start: int = list(non_idle_interval.keys())[0]
            non_idle_interval_end: int = non_idle_interval[non_idle_interval_start]
            non_idle_interval_duration: int = non_idle_interval_end - non_idle_interval_start

            # Get all timestamps from all cores within the non idle interval
            all_timestamps = set()
            for core_df in core_to_profile_data_df.values():
                core_df = core_df[
                    (core_df['Time'] >= non_idle_interval_start) & 
                    (core_df['Time'] <= non_idle_interval_end)
                ]
                all_timestamps.update(core_df['Time'].unique())
            all_timestamps = sorted(list(all_timestamps))

            # Get updated core dfs for this timestamp range
            updated_core_to_profile_data_df: Dict[str, pd.DataFrame] = {}
            for core_id, core_df in core_to_profile_data_df.items():
                core_df = core_df[
                    (core_df['Time'] >= non_idle_interval_start) & 
                    (core_df['Time'] <= non_idle_interval_end)
                ]
                updated_core_to_profile_data_df[core_id] = core_df

            # get core with highest instructions for this trace
            core_with_highest_instructions = None
            max_instructions = 0
            for core_id, core_df in updated_core_to_profile_data_df.items():
                if not core_df.empty:
                    total_instructions = core_df['Instructions'].sum()
                    if total_instructions > max_instructions:
                        max_instructions = total_instructions
                        core_with_highest_instructions = core_id
            if core_with_highest_instructions is None:
                print(f"No instructions data found for trace {trace_id} for non idle interval {i}.")
                continue

            # For each timestamp, sum up LLC loads and misses across all cores
            for timestamp in all_timestamps:
                total_llc_loads = 0
                total_llc_misses = 0
                for core_id, core_df in updated_core_to_profile_data_df.items():
                    if not core_df.empty:
                        timestamp_data = core_df[core_df['Time'] == timestamp]
                        if not timestamp_data.empty:
                            total_llc_loads += timestamp_data['LLC-loads'].iloc[0]
                            total_llc_misses += timestamp_data['LLC-misses'].iloc[0]

                # Get instructions for this timestamp
                instructions_df = updated_core_to_profile_data_df[core_with_highest_instructions]
                if not instructions_df.empty:
                    timestamp_instructions = instructions_df[instructions_df['Time'] == timestamp]['Instructions'].iloc[0] if not instructions_df[instructions_df['Time'] == timestamp].empty else 0
                else:
                    continue

                # Normalize the data
                relative_position = (timestamp - non_idle_interval_start) / non_idle_interval_duration
                relative_position = max(0, min(1, relative_position))
                normalised_perf_data_per_non_idle_interval[i].append({
                    'trace_id': trace_id,
                    'absolute_time': timestamp,
                    'relative_position': relative_position,
                    'LLC-loads': total_llc_loads,
                    'LLC-misses': total_llc_misses,
                    'Instructions': timestamp_instructions,
                    'core_id': core_with_highest_instructions
                })

    if not normalised_perf_data_per_non_idle_interval:
        print("No performance data found within trace windows.")
        return
    
    non_idle_interval_idx_to_time_points: Dict[int, np.ndarray] = {}
    non_idle_interval_idx_to_median_llc_loads: Dict[int, List[float]] = {}
    non_idle_interval_idx_to_median_llc_misses: Dict[int, List[float]] = {}
    non_idle_interval_idx_to_core_id_to_median_instructions: Dict[int, Dict[str, List[float]]] = {}

    for non_idle_interval_idx, median_duration in median_duration_per_non_idle_interval.items():
        num_bin_in_microseconds: int = median_duration
        bin_edges: np.ndarray = np.linspace(0, 1, num_bin_in_microseconds + 1)
        bin_centers: np.ndarray = (bin_edges[:-1] + bin_edges[1:]) / 2
        binned_llc_loads: List[List[float]] = [[] for _ in range(num_bin_in_microseconds)]
        binned_llc_misses: List[List[float]] = [[] for _ in range(num_bin_in_microseconds)]
        binned_instructions: Dict[str, List[List[float]]] = {core_id: [[] for _ in range(num_bin_in_microseconds)] for core_id in core_to_profile_data_df.keys()}

        for row in normalised_perf_data_per_non_idle_interval[non_idle_interval_idx]:
            bin_idx: int = min(int(row['relative_position'] * num_bin_in_microseconds), num_bin_in_microseconds - 1)
            binned_llc_loads[bin_idx].append(row['LLC-loads'])
            binned_llc_misses[bin_idx].append(row['LLC-misses'])
            binned_instructions[row['core_id']][bin_idx].append(row['Instructions'])

        median_llc_loads: List[float] = []
        median_llc_misses: List[float] = []
        core_id_to_instructions: Dict[str, List[float]] = {core_id: [] for core_id in core_to_profile_data_df.keys()}   
        valid_bin_centers: List[float] = []
        for i in range(num_bin_in_microseconds):
            if binned_llc_loads[i] and binned_llc_misses[i]:
                median_llc_loads.append(np.median([x for x in binned_llc_loads[i] if x > 0]))
                median_llc_misses.append(np.median([x for x in binned_llc_misses[i] if x > 0]))
                valid_bin_centers.append(bin_centers[i])
                # Calculate median instructions for each core
                for core_id in core_to_profile_data_df.keys():
                    core_id_to_instructions[core_id].append(
                        np.median([x for x in binned_instructions[core_id][i] if x > 0]) if binned_instructions[core_id][i] else 0
                    )
        time_points: np.ndarray = np.array(valid_bin_centers) * median_duration

        non_idle_interval_idx_to_time_points[non_idle_interval_idx] = time_points
        non_idle_interval_idx_to_median_llc_loads[non_idle_interval_idx] = median_llc_loads
        non_idle_interval_idx_to_median_llc_misses[non_idle_interval_idx] = median_llc_misses
        non_idle_interval_idx_to_core_id_to_median_instructions[non_idle_interval_idx] = core_id_to_instructions

    total_median_duration_across_non_idle_intervals: float = sum(median_duration_per_non_idle_interval.values())

    # Plot the the non idle intervals side by side in one plot for llc loads and misses
    llc_fig: plt.Figure
    llc_axs: plt.Axes
    instruction_fig: plt.Figure
    instruction_ax: plt.Axes
    if len(core_to_profile_data_df) == 1:
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        llc_axs = axes[0]
        llc_fig = fig
        instruction_ax = axes[1]
        instruction_fig = fig
        llc_fig.suptitle(
            f"LLC and Instructions data across Non-Idle Intervals\nContainer: {container_name} | Config: {config}\n{median_non_idle_intervals} Non Idle Intervals | Median Duration: {total_median_duration_across_non_idle_intervals:.3f} μs",
            fontsize=14, fontweight='bold'
        )
    else:
        llc_fig, llc_axs = plt.subplots(figsize=(15, 10))
        llc_fig.suptitle(
            f"LLC across Non-Idle Intervals\nContainer: {container_name} | Config: {config}\n{median_non_idle_intervals} Non Idle Intervals | Median Duration: {total_median_duration_across_non_idle_intervals:.3f} μs",
            fontsize=14, fontweight='bold'
        )

    cumulative_time = 0
    all_time_points = []
    llc_loads_data = []
    llc_misses_data = []
    break_points = []
    x_lim_end = 0
    for idx in range(median_non_idle_intervals):
        time_points = non_idle_interval_idx_to_time_points[idx]
        median_llc_loads = non_idle_interval_idx_to_median_llc_loads[idx]
        median_llc_misses = non_idle_interval_idx_to_median_llc_misses[idx]
        adjusted_time_points = time_points + cumulative_time
        all_time_points.extend(adjusted_time_points)
        llc_loads_data.extend(median_llc_loads)
        llc_misses_data.extend(median_llc_misses)
        x_lim_end = adjusted_time_points[-1] + 10
        if idx < median_non_idle_intervals - 1:
            cumulative_time = adjusted_time_points[-1] + 10
            break_points.append(cumulative_time)

    llc_axs.scatter(all_time_points, llc_loads_data, color='blue', marker='o', s=10, label='LLC Loads', alpha=0.7)
    llc_axs.scatter(all_time_points, llc_misses_data, color='red', marker='^', s=10, label='LLC Misses', alpha=0.7)
    for break_point in break_points:
        llc_axs.axvline(x=break_point, color='gray', linestyle='--', alpha=1)
    llc_axs.set_xlabel("Time (μs)")
    llc_axs.set_ylabel("LLC Loads/Misses")
    llc_axs.set_xlim(0, x_lim_end)
    llc_axs.set_xticks(np.arange(0, x_lim_end, step=100))
    llc_axs.set_title(f"LLC Loads and Misses across Non-Idle Intervals\n{container_name} | {config}")
    llc_axs.legend()
    llc_axs.grid(True, linestyle='--', alpha=0.3)
    llc_axs.legend(loc='upper right')

    if save_median_resource_usage_csvs:
        # Save the LLC data and breakpoints to CSV file
        llc_data_df = pd.DataFrame({
            'Time': all_time_points,
            'LLC-loads': llc_loads_data,
            'LLC-misses': llc_misses_data,
            "is_break_point": [1 if time in break_points else 0 for time in all_time_points]
        })
        llc_data_csv_file_name = f"llc_data_{container_name}_{config}.csv"
        llc_data_df.to_csv(os.path.join(profile_data_dir, llc_data_csv_file_name), index=False)
        print(f"LLC data saved to {llc_data_csv_file_name} in {profile_data_dir}")

    # Plot instructions data
    if len(core_to_profile_data_df) == 1:
        cumulative_time = 0
        x_lim_end = 0
        all_time_points = []
        instructions_data = []
        break_points = []
        
        for idx in range(median_non_idle_intervals):
            time_points = non_idle_interval_idx_to_time_points[idx]
            core_id_to_instructions = non_idle_interval_idx_to_core_id_to_median_instructions[idx]
            adjusted_time_points = time_points + cumulative_time
            all_time_points.extend(adjusted_time_points)
            for core_id, instructions in core_id_to_instructions.items():
                if not instructions:
                    continue
                instructions_data.extend(instructions)
                x_lim_end = adjusted_time_points[-1] + 10
            if idx < median_non_idle_intervals - 1:
                cumulative_time = adjusted_time_points[-1] + 10
                break_points.append(cumulative_time)

        instruction_ax.scatter(all_time_points, instructions_data, color='green', marker='o', s=10, label='Instructions', alpha=0.7)
        for break_point in break_points:
            instruction_ax.axvline(x=break_point, color='gray', linestyle='--', alpha=1)
        instruction_ax.set_title(f"Instructions across Non-Idle Intervals\n{container_name} | {config}")
        instruction_ax.set_xlabel('Time (μs)', fontsize=10)
        instruction_ax.set_ylabel('Instructions', fontsize=10)
        instruction_ax.set_xlim(0, x_lim_end)
        instruction_ax.set_xticks(np.arange(0, x_lim_end, step=100))
        instruction_ax.grid(True, linestyle='--', alpha=0.3)
        instruction_ax.legend(loc='upper right')

        llc_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        llc_instructions_png_file_name = f"llc_instructions_{container_name}_{config}.png"
        llc_fig.savefig(os.path.join(output_dir, llc_instructions_png_file_name))
        plt.close(llc_fig)
        print(f"Aligned median resource usage plot saved as {llc_instructions_png_file_name} in {output_dir}")
    else:
        # TODO: revisit, might be buggy
        instruction_fig, instruction_axes = plt.subplots(len(core_to_profile_data_df), 1, figsize=(15, 10))
        instruction_fig.suptitle(
            f"Instructions across Non-Idle Intervals\nContainer: {container_name} | Config: {config}\n{median_non_idle_intervals} Non Idle Intervals | Median Duration: {total_median_duration_across_non_idle_intervals:.3f} μs",
            fontsize=14, fontweight='bold'
        )
        for i, (core_id, core_id_to_instructions) in enumerate(non_idle_interval_idx_to_core_id_to_median_instructions.items()):
            core_ax = instruction_axes[i]
            cumulative_time = 0
            for idx in range(median_non_idle_intervals):
                time_points = non_idle_interval_idx_to_time_points[idx]
                instructions = core_id_to_instructions[idx]
                adjusted_time_points = time_points + cumulative_time
                core_ax.scatter(adjusted_time_points, instructions, color='blue', s=10, alpha=0.7)
                for i, instruction in enumerate(instructions):
                    instructions_data.append({
                        'Time': adjusted_time_points[i],
                        'Core ID': core_id,
                        'Instructions': instruction
                    })
                if idx < median_non_idle_intervals - 1:
                    cumulative_time = adjusted_time_points[-1] + 10 # Add a small gap between intervals
                    core_ax.axvline(x=cumulative_time, color='r', linestyle='--', alpha=1)
            core_ax.set_xlabel('Time (μs)', fontsize=10)
            core_ax.set_ylabel('Instructions', fontsize=10)
            core_ax.set_xlim(0, cumulative_time + 10)
            core_ax.set_xticks(np.arange(0, cumulative_time + 10, step=100))
            core_ax.set_ylim(0, max(max(instructions) for instructions in core_id_to_instructions.values()) * 1.1)
            core_ax.grid(True, linestyle='--', alpha=0.3)
            core_ax.legend(loc='upper right')
            core_ax.set_title(f"Core {core_id} Instructions", fontsize=12, fontweight='bold')

            llc_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            llc_png_file_name = f"llc_{container_name}_{config}.png"
            llc_fig.savefig(os.path.join(output_dir, llc_png_file_name))
            plt.close(llc_fig)
            instruction_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            instruction_png_file_name = f"instructions_{container_name}_{config}.png"
            instruction_fig.savefig(os.path.join(output_dir, instruction_png_file_name))
            plt.close(instruction_fig)
            print(f"Aligned median resource usage plots saved as {llc_png_file_name} and {instruction_png_file_name} in {output_dir}")

    if save_median_resource_usage_csvs:
        # Save the instructions data to CSV file
        instructions_data_df = pd.DataFrame(instructions_data)
        instructions_data_csv_file_name = f"instructions_data_{container_name}_{config}.csv"
        instructions_data_df.to_csv(os.path.join(profile_data_dir, instructions_data_csv_file_name), index=False)
        print(f"Instructions data saved to {instructions_data_csv_file_name} in {profile_data_dir}")
    
    print(f"Number of traces analysed: {len(trace_id_to_non_idle_intervals)}")

def get_highest_resource_usage_traces(
    trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]],
    core_to_profile_data_df: Dict[str, pd.DataFrame],
    num_samples: int
) -> pd.DataFrame:
    trace_stats = []
    min_perf_time = min([df['Time'].min() for df in core_to_profile_data_df.values()])
    max_perf_time = max([df['Time'].max() for df in core_to_profile_data_df.values()])
    
    for trace_id, non_idle_intervals in trace_id_to_non_idle_intervals.items():
        non_idle_intervals = sorted(non_idle_intervals, key=lambda x: list(x.keys())[0])
        trace_start = list(non_idle_intervals[0].keys())[0]
        trace_end = list(non_idle_intervals[-1].values())[0]
        duration = trace_end - trace_start
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
                
        if curr_core_with_highest_instructions is None:
            print(f"No instructions data found for trace {trace_id}.")
            continue

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
    trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]],
    core_to_profile_data_df: Dict[str, pd.DataFrame],
    output_dir: str
) -> None:
    num_cores = len(core_to_profile_data_df)
    fig, axs = plt.subplots(num_cores, 1, figsize=(15, 4*num_cores))
    fig.suptitle("Instructions per Core with Trace Start/End Times", fontsize=14, fontweight='bold')

    if num_cores == 1:
        axs = [axs]

    for i, (core_id, perf_df) in enumerate(core_to_profile_data_df.items()):
        ax = axs[i]
        ax.plot(perf_df['Time'], perf_df['Instructions'], label=f'Core {core_id} Instructions', color='blue', alpha=0.7)
        for trace_id, non_idle_intervals in trace_id_to_non_idle_intervals.items():
            non_idle_intervals = sorted(non_idle_intervals, key=lambda x: list(x.keys())[0])
            trace_start = list(non_idle_intervals[0].keys())[0]
            trace_end = list(non_idle_intervals[-1].values())[0]
            ax.axvline(x=trace_start, color='red', linestyle='--', alpha=0.5)
            ax.axvline(x=trace_end, color='blue', linestyle='--', alpha=0.5)
            ax.axvspan(trace_start, trace_end, alpha=0.3, color='green', label=f'Trace {trace_id}')
        ax.set_title(f'Core {core_id} Instructions')
        ax.set_xlabel('Time (μs)')
        ax.set_ylabel('Instructions')
        ax.grid(True)

    plt.tight_layout()
    plot_path = os.path.join(output_dir, 'traces_instructions_plot.png')
    plt.savefig(plot_path, bbox_inches='tight')
    plt.close()
    print(f"Plot saved to {plot_path}")

def plot_highest_resource_usage_traces(
    trace_stats_df: pd.DataFrame,
    cores_to_profile_data_df: Dict[str, pd.DataFrame],
    output_dir: str,
    num_samples: int,
    config: str,
    container_name: str
) -> None:
    num_plots = 0
    print(f"Plotting top {min(num_samples, len(trace_stats_df))} traces by resource usage")

    for i, trace in trace_stats_df.iterrows():
        if num_plots == num_samples:
            break
        trace_id = trace["trace_id"]
        trace_start = trace["start_time"]
        trace_end = trace["end_time"]
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
                cache_partitions_str = part[2:]
                break
        fig, axs = plt.subplots(2, 1, figsize=(15, 10))
        trace_duration = trace_end - trace_start
        fig.suptitle(
            f"Container: {container_name} | Cache Partitons: {cache_partitions_str}\nTotal Trace Duration: {trace_duration} μs ",
            fontsize=14, fontweight='bold'
        )

        min_time = zoomed_plot_profile_df["Time"].min()
        zoomed_plot_profile_df["NormalizedTime"] = zoomed_plot_profile_df["Time"] - min_time
        normalized_trace_start = trace_start - min_time
        normalized_trace_end = trace_end - min_time

        axs[0].scatter(zoomed_plot_profile_df["NormalizedTime"], zoomed_plot_profile_df['LLC-loads'], s=10, alpha=0.7, color="blue", label="LLC Loads")
        axs[0].scatter(zoomed_plot_profile_df["NormalizedTime"], zoomed_plot_profile_df['LLC-misses'], s=10, alpha=0.7, color="red", label="LLC Misses")
        axs[0].axvspan(normalized_trace_start, normalized_trace_end, alpha=0.2, color=(1, 0.7, 0.7), label="Trace Window")
        axs[0].set_title("LLC Loads and LLC Misses (Zoomed In)")
        axs[0].set_xlabel("Time (microseconds)")
        axs[0].set_ylabel("Count")
        axs[0].legend()

        axs[1].scatter(zoomed_plot_profile_df["NormalizedTime"], zoomed_plot_profile_df['Instructions'], s=10, alpha=0.7, color="green", label="Instructions")
        axs[1].axvspan(normalized_trace_start, normalized_trace_end, alpha=0.2, color=(1, 0.7, 0.7), label="Trace Window")
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
    save_median_resource_usage_csvs: bool = args.save_median_resource_usage_csvs
    
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
    
    print("\nContainer Jaeger Traces Data:")
    print(container_jaeger_traces_df.head())
    print("Cores to Profile Data:")
    for core_id, core_df in cores_to_profile_data_df.items():
        print(f"Core {core_id} Profile Data:")
        print(core_df.head())
    
    edt = ZoneInfo("America/New_York")
    min_perf_time = min([df['Time'].min() for df in cores_to_profile_data_df.values()])
    max_perf_time = max([df['Time'].max() for df in cores_to_profile_data_df.values()])
    min_trace_time = container_jaeger_traces_df['start_time'].min()
    max_trace_time = container_jaeger_traces_df['end_time'].max()
    min_perf_time_dt = datetime.fromtimestamp(min_perf_time / 1e6, tz=timezone.utc).astimezone(edt)
    max_perf_time_dt = datetime.fromtimestamp(max_perf_time / 1e6, tz=timezone.utc).astimezone(edt)
    min_trace_time_dt = datetime.fromtimestamp(min_trace_time / 1e6, tz=timezone.utc).astimezone(edt)
    max_trace_time_dt = datetime.fromtimestamp(max_trace_time / 1e6, tz=timezone.utc).astimezone(edt)
    print(f"Performance data time range [{min_perf_time_dt} - {max_perf_time_dt}] aka [{min_perf_time} - {max_perf_time}]")
    print(f"Trace data time range [{min_trace_time_dt} - {max_trace_time_dt}] aka [{min_trace_time} - {max_trace_time}]")

    all_trace_ids_to_non_idle_intervals: Dict[str, List[Dict[int, int]]] = get_trace_id_to_non_idle_intervals(container_jaeger_traces_df)
    if not all_trace_ids_to_non_idle_intervals:
        print("No non-idle intervals found in traces.")
        return
    
    print("\nPlotting traces start/end times and performance data...")
    plot_traces_start_end_times_and_perf_data(
        all_trace_ids_to_non_idle_intervals,
        cores_to_profile_data_df,
        plot_dir
    )
    
    median_non_idle_intervals = get_median_non_idle_intervals(all_trace_ids_to_non_idle_intervals)
    # filter out traces with non idle intervals not equal to median
    filtered_trace_ids_to_non_idle_intervals = {trace_id: non_idle_intervals for trace_id, non_idle_intervals in all_trace_ids_to_non_idle_intervals.items() if len(non_idle_intervals) == median_non_idle_intervals}
    if not filtered_trace_ids_to_non_idle_intervals:
        print(f"No traces found with {median_non_idle_intervals} number of non idle intervals.")
        return
    
    median_duration_per_non_idle_interval, non_idle_duration_index_to_trace_id_non_idle_duration_map = get_median_duration_information_for_non_idle_intervals(filtered_trace_ids_to_non_idle_intervals, median_non_idle_intervals)
    selected_trace_ids = get_selected_traces_based_non_median_non_idle_intervals(
        median_duration_per_non_idle_interval,
        non_idle_duration_index_to_trace_id_non_idle_duration_map,
        median_non_idle_intervals
    )
    # filter out traces with trace ids not in selected_trace_ids
    final_trace_ids_to_non_idle_intervals = {trace_id: non_idle_intervals for trace_id, non_idle_intervals in filtered_trace_ids_to_non_idle_intervals.items() if trace_id in selected_trace_ids}
    if not filtered_trace_ids_to_non_idle_intervals:
        print("No traces found after filtering by median duration +- 1 standard deviation.")
        return

    print("\nPlotting aligned median resource usage...")
    plot_aligned_median_resource_usage(
        final_trace_ids_to_non_idle_intervals,
        median_non_idle_intervals,
        median_duration_per_non_idle_interval,
        cores_to_profile_data_df,
        profile_data_dir,
        plot_dir,
        config,
        container_name,
        save_median_resource_usage_csvs
    )

    print("\nGetting highest resource usage traces...")
    highest_resource_usage_traces = get_highest_resource_usage_traces(
        final_trace_ids_to_non_idle_intervals,
        cores_to_profile_data_df,
        samples
    )
    if highest_resource_usage_traces.empty:
        print("No traces found with performance data.")
        return

    print("\nPlotting profile for highest resource usage traces...")
    plot_highest_resource_usage_traces(
        highest_resource_usage_traces, 
        cores_to_profile_data_df, 
        plot_dir, 
        samples, 
        config, 
        container_name
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
    
    print("\nPlot generation complete.")

if __name__ == "__main__":
    main()