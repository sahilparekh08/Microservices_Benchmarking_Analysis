"""
Functions for plotting and visualizing trace and performance data.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import Dict, Any, List
import math

from .trace_processor import get_non_overlapping_longest_durations

def plot_aligned_median_resource_usage(
    traces_df: pd.DataFrame, 
    profile_df: pd.DataFrame, 
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

def plot_traces_start_end_times_and_perf_data(
    traces_df: pd.DataFrame,
    profile_df: pd.DataFrame,
    output_dir: str
) -> None:
    """Plot trace start/end times and performance data."""
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
    """Plot performance profiles with trace data."""
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