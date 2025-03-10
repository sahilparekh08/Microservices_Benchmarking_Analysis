import argparse
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, List, Dict
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from matplotlib.patches import Rectangle

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Jaeger trace data for a given service.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Test configuration")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--samples-per-operation", type=int, default=3, help="Number of samples per operation")
    parser.add_argument("--plot-dir", type=str, default="outputs", help="Output directory for plots")
    return parser.parse_args()

def load_traces_data(
    data_dir: str,
    service_name_for_traces: str,
    test_name: str,
    config: str,
    container_name: str
) -> pd.DataFrame:
    jaeger_traces_csv_file_path: str = os.path.join(data_dir, "data",
                                                   f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    jaeger_traces_df: pd.DataFrame = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df: pd.DataFrame = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    return container_jaeger_traces_df

def load_perf_data(data_dir: str) -> pd.DataFrame:
    llc_data_file: str = f"{data_dir}/data/perf_data.csv"
    df: pd.DataFrame = pd.read_csv(llc_data_file, sep=",")
    return df

def get_samples_per_operation(traces_df: pd.DataFrame, samples_per_operation: int) -> pd.DataFrame:
    operations = traces_df['operation'].unique()
    sampled_traces = []
    
    for operation in operations:
        operation_traces = traces_df[traces_df['operation'] == operation]
        n_samples = min(samples_per_operation, len(operation_traces))
        if n_samples > 0:
            if len(operation_traces) > 1000:
                sampled_indices = random.sample(range(len(operation_traces)), n_samples)
                sampled_traces.append(operation_traces.iloc[sampled_indices])
            else:
                sampled_traces.append(operation_traces.sample(n=n_samples))
    
    return pd.concat(sampled_traces, ignore_index=True) if sampled_traces else pd.DataFrame()

def process_perf_df(raw_perf_df: pd.DataFrame) -> pd.DataFrame:
    processed_df = pd.DataFrame()
    processed_df['Time'] = raw_perf_df['Time'].astype(int)
    
    processed_df['llc_loads'] = 0
    processed_df['llc_misses'] = 0
    processed_df['instructions'] = 0
    
    for time, group in raw_perf_df.groupby('Time'):
        for _, row in group.iterrows():
            if row['Type'] == 'INSTRUCTIONS':
                processed_df.loc[processed_df['Time'] == time, 'instructions'] = row['Frequency']
            elif row['Type'] == 'LOAD':
                processed_df.loc[processed_df['Time'] == time, 'llc_loads'] = row['Frequency']
            elif row['Type'] == 'MISS':
                processed_df.loc[processed_df['Time'] == time, 'llc_misses'] = row['Frequency']
    
    processed_df.sort_values('Time', inplace=True)
    processed_df.reset_index(drop=True, inplace=True)
    
    return processed_df

def extend_perf_data_for_trace(perf_df: pd.DataFrame, start_time_us: float, end_time_us: float) -> pd.DataFrame:
    if perf_df.empty:
        return pd.DataFrame({
            'Time': [start_time_us, end_time_us],
            'llc_loads': [0, 0],
            'llc_misses': [0, 0],
            'instructions': [0, 0]
        })
    
    min_time = perf_df['Time'].min()
    max_time = perf_df['Time'].max()
    extended_df = perf_df.copy()
    
    if start_time_us < min_time:
        first_row = perf_df.iloc[0].copy()
        first_row['Time'] = start_time_us
        extended_df = pd.concat([pd.DataFrame([first_row]), extended_df], ignore_index=True)
    
    if end_time_us > max_time:
        last_row = perf_df.iloc[-1].copy()
        last_row['Time'] = end_time_us
        extended_df = pd.concat([extended_df, pd.DataFrame([last_row])], ignore_index=True)
    
    return extended_df.sort_values('Time').reset_index(drop=True)

def get_perf_metrics_for_trace(processed_perf_df: pd.DataFrame, start_time_us: float, end_time_us: float) -> pd.DataFrame:
    filtered_perf = processed_perf_df[
        (processed_perf_df['Time'] >= start_time_us) & 
        (processed_perf_df['Time'] <= end_time_us)
    ]
    
    if filtered_perf.empty or filtered_perf['Time'].min() > start_time_us or filtered_perf['Time'].max() < end_time_us:
        print(f"Warning: No perf data found for trace between {start_time_us} and {end_time_us}. Extending data.")
        filtered_perf = extend_perf_data_for_trace(filtered_perf, start_time_us, end_time_us)
    
    return filtered_perf

def parse_non_idle_intervals(intervals_str: str) -> List[Tuple[float, float]]:
    if pd.isna(intervals_str) or intervals_str == '':
        return []
    
    intervals = []
    parts = intervals_str.split(';')
    for part in parts:
        if '-' in part:
            start_str, end_str = part.split('-')
            try:
                start = float(start_str)
                end = float(end_str)
                intervals.append((start, end))
            except ValueError:
                print(f"Warning: Could not parse interval '{part}'")
    
    return intervals

def plot_trace_perf_metrics(
    trace_row: pd.Series, 
    perf_data: pd.DataFrame, 
    output_dir: str,
    non_idle_intervals: List[Tuple[float, float]]
) -> str:
    trace_id = trace_row['trace_id']
    operation_name = trace_row['operation']
    service_name = trace_row['service']
    
    safe_operation = operation_name.replace("/", "_").replace(" ", "_")
    filename = f"{safe_operation}_{trace_id}.png"
    filepath = os.path.join(output_dir, filename)
    
    if perf_data.empty:
        return f"No data found for {trace_id}"
    
    start_time = trace_row['start_time']
    end_time = trace_row['end_time']
    
    perf_data = perf_data.copy()
    
    fig, axs = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    
    axs[0].plot(perf_data['Time'], perf_data['llc_loads'], 'b-')
    axs[0].set_title(f'LLC Loads - {operation_name} ({service_name})')
    axs[0].set_ylabel('LLC Loads (cumulative)')
    axs[0].grid(True)
    
    axs[1].plot(perf_data['Time'], perf_data['llc_misses'], 'r-')
    axs[1].set_title('LLC Misses')
    axs[1].set_ylabel('LLC Misses (cumulative)')
    axs[1].grid(True)
    
    axs[2].plot(perf_data['Time'], perf_data['instructions'], 'g-')
    axs[2].set_title('Instructions')
    axs[2].set_ylabel('Instructions (cumulative)')
    axs[2].set_xlabel('Time (microseconds) absolute')
    axs[2].grid(True)
    
    for ax in axs:
        ax.axvline(x=start_time, color='green', linestyle='--', linewidth=1.5, label='Start')
        ax.axvline(x=end_time, color='red', linestyle='--', linewidth=1.5, label='End')
        
        for period_start, period_end in non_idle_intervals:
            width = period_end - period_start
            rect = Rectangle((period_start, ax.get_ylim()[0]), width, 
                            ax.get_ylim()[1] - ax.get_ylim()[0],
                            color='yellow', alpha=0.3)
            ax.add_patch(rect)
    
    handles, labels = axs[0].get_legend_handles_labels()
    if handles:
        axs[0].legend()
    
    total_non_idle_time = sum([end - start for start, end in non_idle_intervals])
    non_idle_percentage = (total_non_idle_time / (end_time - start_time)) * 100 if end_time > start_time else 0
    
    duration_us = trace_row['duration']
    textstr = (
        f"Trace ID: {trace_id}\n"
        f"Duration: {duration_us} µs\n"
        f"Start: {start_time} µs\n"
        f"End: {end_time} µs\n"
        f"Non-idle time: {total_non_idle_time:.2f} µs ({non_idle_percentage:.1f}%)\n"
        f"Non-idle intervals: {len(non_idle_intervals)}"
    )
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    fig.text(0.05, 0.95, textstr, fontsize=10, verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close(fig)
    
    return filepath

def plot_combined_operation_traces(
    traces_df: pd.DataFrame,
    processed_perf_df: pd.DataFrame,
    operation_name: str,
    output_dir: str
) -> str:
    operation_traces = traces_df[traces_df['operation'] == operation_name]
    if operation_traces.empty:
        return None
    
    safe_operation = operation_name.replace("/", "_").replace(" ", "_")
    filename = f"{safe_operation}_combined.png"
    filepath = os.path.join(output_dir, filename)
    
    global_min_time = operation_traces['start_time'].min()
    global_max_time = operation_traces['end_time'].max()
    
    global_perf_data = processed_perf_df[
        (processed_perf_df['Time'] >= global_min_time) & 
        (processed_perf_df['Time'] <= global_max_time)
    ].copy()
    
    if global_perf_data.empty:
        global_perf_data = extend_perf_data_for_trace(global_perf_data, global_min_time, global_max_time)
    
    colors = plt.cm.tab10.colors
    
    fig, axs = plt.subplots(3, 1, figsize=(14, 18), sharex=True)
    
    axs[0].plot(global_perf_data['Time'], global_perf_data['llc_loads'], 'b-', alpha=0.3)
    axs[0].set_title(f'LLC Loads - {operation_name} (Combined Traces)')
    axs[0].set_ylabel('LLC Loads (cumulative)')
    axs[0].grid(True)
    
    axs[1].plot(global_perf_data['Time'], global_perf_data['llc_misses'], 'r-', alpha=0.3)
    axs[1].set_title('LLC Misses')
    axs[1].set_ylabel('LLC Misses (cumulative)')
    axs[1].grid(True)
    
    axs[2].plot(global_perf_data['Time'], global_perf_data['instructions'], 'g-', alpha=0.3)
    axs[2].set_title('Instructions')
    axs[2].set_xlabel('Time (microseconds) absolute')
    axs[2].set_ylabel('Instructions (cumulative)')
    axs[2].grid(True)
    
    legend_handles = []
    for i, (_, trace) in enumerate(operation_traces.iterrows()):
        color = colors[i % len(colors)]
        trace_id = trace['trace_id']
        start_time = trace['start_time']
        end_time = trace['end_time']
        
        non_idle_intervals = parse_non_idle_intervals(trace['non_idle_intervals'])
        
        for ax in axs:
            start_line = ax.axvline(x=start_time, color=color, linestyle='--', linewidth=1.5)
            ax.axvline(x=end_time, color=color, linestyle=':', linewidth=1.5)
            
            for period_start, period_end in non_idle_intervals:
                width = period_end - period_start
                rect = Rectangle((period_start, ax.get_ylim()[0]), width, 
                                ax.get_ylim()[1] - ax.get_ylim()[0],
                                color=color, alpha=0.2)
                ax.add_patch(rect)
        
        if i == 0:
            legend_handles.append(start_line)
        else:
            legend_handles.append(start_line)
    
    trace_names = [f"Trace {i+1}: {row['trace_id']}" for i, (_, row) in enumerate(operation_traces.iterrows())]
    axs[0].legend(legend_handles, trace_names, loc='upper left')
    
    summary_text = f"Operation: {operation_name}\nNumber of Traces: {len(operation_traces)}"
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    fig.text(0.05, 0.95, summary_text, fontsize=10, verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close(fig)
    
    return filepath

def generate_plots(
    traces_df: pd.DataFrame,
    raw_perf_df: pd.DataFrame,
    samples_per_operation: int,
    output_dir: str
) -> None:
    processed_perf_df = process_perf_df(raw_perf_df)

    edt = ZoneInfo("America/New_York")
    perf_start_time = datetime.fromtimestamp(processed_perf_df['Time'].min() / 1e6, tz=timezone.utc).astimezone(edt)
    perf_end_time = datetime.fromtimestamp(processed_perf_df['Time'].max() / 1e6, tz=timezone.utc).astimezone(edt)
    traces_start_time = datetime.fromtimestamp(traces_df['start_time'].min() / 1e6, tz=timezone.utc).astimezone(edt)
    traces_end_time = datetime.fromtimestamp(traces_df['end_time'].max() / 1e6, tz=timezone.utc).astimezone(edt)
    print(f"Loaded perf values between [{perf_start_time} / {processed_perf_df['Time'].min()}] and [{perf_end_time} / {processed_perf_df['Time'].max()}]")
    print(f"Loaded Jaeger traces between [{traces_start_time} / {traces_df['start_time'].min()}] and [{traces_end_time} / {traces_df['end_time'].max()}]")

    sampled_traces = get_samples_per_operation(traces_df, samples_per_operation)
    
    if sampled_traces.empty:
        print("No traces found matching the criteria")
        return
    
    combined_dir = os.path.join(output_dir, "combined")
    os.makedirs(combined_dir, exist_ok=True)
    
    for _, trace in sampled_traces.iterrows():
        start_time = trace['start_time']
        end_time = trace['end_time']

        print(f"Processing trace {trace['trace_id']} for {trace['operation']} ({trace['service']}) with start time {start_time} and end time {end_time}")
        
        trace_perf_data = get_perf_metrics_for_trace(processed_perf_df, start_time, end_time)
        
        non_idle_intervals = parse_non_idle_intervals(trace['non_idle_intervals'])
        print(f"Found {len(non_idle_intervals)} non-idle intervals from trace data")
        
        plot_path = plot_trace_perf_metrics(trace, trace_perf_data, output_dir, non_idle_intervals)
        print(f"Generated plot: {plot_path}")
    
    operations = sampled_traces['operation'].unique()
    for operation in operations:
        print(f"Creating combined plot for operation: {operation}")
        combined_plot_path = plot_combined_operation_traces(
            sampled_traces, processed_perf_df, operation, combined_dir)
        
        if combined_plot_path:
            print(f"Generated combined plot: {combined_plot_path}")

def main() -> None:
    args: argparse.Namespace = parse_arguments()
    test_name: str = args.test_name.replace(" ", "_")
    service_name_for_traces: str = args.service_name_for_traces
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    samples_per_operation: int = args.samples_per_operation
    plot_dir: str = args.plot_dir
    
    print(f"Test Name: {test_name}")
    print(f"Service Name for Traces: {service_name_for_traces}")
    print(f"Container Name: {container_name}")
    print(f"Config: {config}")
    print(f"Data Directory: {data_dir}")
    print(f"Samples per Operation: {samples_per_operation}")
    print(f"Plot Directory: {plot_dir}")
    
    os.makedirs(plot_dir, exist_ok=True)
    
    container_jaeger_traces_df: pd.DataFrame = load_traces_data(
        data_dir, service_name_for_traces, test_name, config, container_name)
    perf_df: pd.DataFrame = load_perf_data(data_dir)
    
    print(f"Loaded {len(container_jaeger_traces_df)} traces and {len(perf_df)} perf data points")
    
    generate_plots(
        container_jaeger_traces_df, 
        perf_df, 
        samples_per_operation,
        plot_dir
    )
    
    print("Plot generation complete.")

if __name__ == "__main__":
    main()
