"""
Functions for plotting and visualizing trace and performance data.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Dict, Any, List
import math
import os

from ..data_processing.trace_processor import get_non_overlapping_longest_durations

def plot_aligned_median_resource_usage(
    traces_df: pd.DataFrame, 
    core_to_perf_data_df: Dict[str, pd.DataFrame],
    output_dir: str, 
    config: str, 
    container_name: str, 
    service_name_for_traces: str
) -> None:
    """Plot aligned median resource usage across traces."""
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
        
        # Get all timestamps from all cores within the trace window
        all_timestamps = set()
        for core_df in core_to_perf_data_df.values():
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
            
            for core_df in core_to_perf_data_df.values():
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
            
            for core_id, core_df in core_to_perf_data_df.items():
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
                
            instructions_df = core_to_perf_data_df[core_with_highest_instructions]
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
    binned_instructions: Dict[str, List[List[float]]] = {core_id: [[] for _ in range(num_bins_in_microseconds)] for core_id in core_to_perf_data_df.keys()}
    
    for _, row in norm_df.iterrows():
        bin_idx: int = min(int(row['relative_position'] * num_bins_in_microseconds), num_bins_in_microseconds - 1)
        binned_llc_loads[bin_idx].append(row['LLC-loads'])
        binned_llc_misses[bin_idx].append(row['LLC-misses'])
        binned_instructions[row['core_id']][bin_idx].append(row['Instructions'])
    
    median_llc_loads: List[float] = []
    median_llc_misses: List[float] = []
    median_instructions: Dict[str, List[float]] = {core_id: [] for core_id in core_to_perf_data_df.keys()}
    valid_bin_centers: List[float] = []
    
    for i in range(num_bins_in_microseconds):
        if binned_llc_loads[i] and binned_llc_misses[i]:
            median_llc_loads.append(np.median([x for x in binned_llc_loads[i] if x > 0]))
            median_llc_misses.append(np.median([x for x in binned_llc_misses[i] if x > 0]))
            valid_bin_centers.append(bin_centers[i])
            
            # Calculate median instructions for each core
            for core_id in core_to_perf_data_df.keys():
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
    colors = plt.cm.Set3(np.linspace(0, 1, len(core_to_perf_data_df)))
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

def plot_traces_start_end_times_and_perf_data(
    traces_df: pd.DataFrame,
    core_to_perf_data_df: Dict[str, pd.DataFrame],
    output_dir: str
) -> None:
    """Plot trace start/end times and performance data."""
    # Get non-overlapping spans with largest durations for each trace
    non_overlapping_traces_df = get_non_overlapping_longest_durations(traces_df)

    # Create a figure with subplots for each core
    num_cores = len(core_to_perf_data_df)
    fig, axs = plt.subplots(num_cores, 1, figsize=(15, 4*num_cores))
    fig.suptitle("Instructions per Core with Trace Start/End Times", fontsize=14, fontweight='bold')

    # If there's only one core, axs will be a single Axes object, not an array
    if num_cores == 1:
        axs = [axs]

    # Plot instructions for each core
    for i, (core_id, perf_df) in enumerate(core_to_perf_data_df.items()):
        ax = axs[i]
        
        # Plot instructions for this core
        ax.plot(perf_df['Time'], perf_df['Instructions'], label=f'Core {core_id} Instructions', color='blue', alpha=0.7)
        
        # Plot trace start/end times as vertical lines
        for _, trace in non_overlapping_traces_df.iterrows():
            trace_start = trace['start_time']
            trace_end = trace['end_time']
            trace_id = trace['trace_id']
            
            # Add vertical lines for trace start and end
            ax.axvline(x=trace_start, color='red', linestyle='--', alpha=0.5)
            ax.axvline(x=trace_end, color='red', linestyle='--', alpha=0.5)
            
            # Add a shaded region for the trace duration
            ax.axvspan(trace_start, trace_end, alpha=0.1, color='red', label=f'Trace {trace_id}')
        
        ax.set_title(f'Core {core_id} Instructions')
        ax.set_xlabel('Time (μs)')
        ax.set_ylabel('Instructions')
        ax.grid(True)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    # Adjust layout to prevent overlap
    plt.tight_layout()
    
    # Save the plot
    plot_path = os.path.join(output_dir, 'traces_instructions_plot.png')
    plt.savefig(plot_path, bbox_inches='tight')
    plt.close()

    print(f"Plot saved to {plot_path}")

def plot_profile_with_traces(
    trace_stats_df: pd.DataFrame,
    core_to_perf_data_df: Dict[str, pd.DataFrame],
    output_dir: str,
    num_samples: int,
    config: str,
    container_name: str,
    service_name_for_traces: str
) -> None:
    """Plot performance profiles with trace data."""
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

        profile_df = core_to_perf_data_df[core_with_highest_instructions]
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

        # Sum up LLC loads and misses across all cores for the trace time window
        total_llc_loads = pd.Series(0, index=zoomed_plot_profile_df.index)
        total_llc_misses = pd.Series(0, index=zoomed_plot_profile_df.index)
        
        for core_id, core_df in core_to_perf_data_df.items():
            core_df = core_df[
                (core_df["Time"] >= trace_start - zoom_margin) &
                (core_df["Time"] <= trace_end + zoom_margin)
            ]
            core_df = core_df.sort_values(by="Time")
            
            # Align the data by time
            core_df = core_df.set_index("Time")
            total_llc_loads += core_df["LLC-loads"].reindex(zoomed_plot_profile_df["Time"]).fillna(0)
            total_llc_misses += core_df["LLC-misses"].reindex(zoomed_plot_profile_df["Time"]).fillna(0)

        # Set the summed values back to the DataFrame
        zoomed_plot_profile_df["LLC-loads"] = total_llc_loads.values
        zoomed_plot_profile_df["LLC-misses"] = total_llc_misses.values
        zoomed_plot_profile_df["Instructions"] = zoomed_plot_profile_df["Instructions"].astype(int)

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
        axs[1].set_title("Instructions (Zoomed In)")
        axs[1].set_xlabel("Time (microseconds)")
        axs[1].set_ylabel("Count")
        axs[1].legend()

        plt.tight_layout()
        plt.savefig(f"{output_dir}/trace_{num_plots+1}_{config}_zoomed_perf_plot.png")
        plt.close()

        num_plots += 1

        print(f"Plot {num_plots} saved: trace_id={trace_id}, resource_usage={total_resource_usage}") 