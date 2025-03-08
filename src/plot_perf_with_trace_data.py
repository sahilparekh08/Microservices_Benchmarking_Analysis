import argparse
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, List, Dict
import random
from datetime import datetime

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

def get_perf_metrics_for_trace(processed_perf_df: pd.DataFrame, start_time_us: float, end_time_us: float) -> pd.DataFrame:
    filtered_perf = processed_perf_df[
        (processed_perf_df['Time'] >= start_time_us) & 
        (processed_perf_df['Time'] <= end_time_us)
    ]
    return filtered_perf

def calculate_perf_metrics(perf_data: pd.DataFrame) -> Dict[str, float]:
    metrics = {}
    
    if perf_data.empty:
        return {
            'llc_loads_delta': 0,
            'llc_misses_delta': 0,
            'instructions_delta': 0,
            'llc_miss_rate': 0
        }
    
    first_row = perf_data.iloc[0]
    last_row = perf_data.iloc[-1]
    
    llc_loads_delta = last_row['llc_loads'] - first_row['llc_loads']
    llc_misses_delta = last_row['llc_misses'] - first_row['llc_misses']
    instructions_delta = last_row['instructions'] - first_row['instructions']
    
    llc_miss_rate = llc_misses_delta / llc_loads_delta if llc_loads_delta > 0 else 0
    
    return {
        'llc_loads_delta': llc_loads_delta,
        'llc_misses_delta': llc_misses_delta,
        'instructions_delta': instructions_delta,
        'llc_miss_rate': llc_miss_rate
    }

def plot_trace_perf_metrics(
    trace_row: pd.Series, 
    perf_data: pd.DataFrame, 
    output_dir: str
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
    perf_data = perf_data.copy()
    perf_data['Time_plot'] = perf_data['Time'] - start_time
    
    fig, axs = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    
    axs[0].plot(perf_data['Time_plot'], perf_data['llc_loads'], 'b-')
    axs[0].set_title(f'LLC Loads - {operation_name} ({service_name})')
    axs[0].set_ylabel('LLC Loads (cumulative)')
    axs[0].grid(True)
    
    axs[1].plot(perf_data['Time_plot'], perf_data['llc_misses'], 'r-')
    axs[1].set_title('LLC Misses')
    axs[1].set_ylabel('LLC Misses (cumulative)')
    axs[1].grid(True)
    
    axs[2].plot(perf_data['Time_plot'], perf_data['instructions'], 'g-')
    axs[2].set_title('Instructions')
    axs[2].set_xlabel('Time (microseconds) relative to trace start')
    axs[2].set_ylabel('Instructions (cumulative)')
    axs[2].grid(True)
    
    duration_us = trace_row['duration']
    textstr = (
        f"Trace ID: {trace_id}\n"
        f"Duration: {duration_us} µs\n"
        f"Start: {start_time} µs\n"
        f"End: {trace_row['end_time']} µs"
    )
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    fig.text(0.05, 0.95, textstr, fontsize=10, verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close(fig)
    
    return filepath

def analyze_traces_with_perf_data(
    traces_df: pd.DataFrame,
    raw_perf_df: pd.DataFrame,
    samples_per_operation: int,
    output_dir: str
) -> pd.DataFrame:
    processed_perf_df = raw_perf_df.sort_values('Time')
    print(f"Loaded perf values between {processed_perf_df['Time'].min()} and {processed_perf_df['Time'].max()}")

    sampled_traces = get_samples_per_operation(traces_df, samples_per_operation)
    
    if sampled_traces.empty:
        print("No traces found matching the criteria")
        return pd.DataFrame()
    
    results = []
    
    for _, trace in sampled_traces.iterrows():
        start_time = trace['start_time']
        end_time = trace['end_time']

        print(f"Processing trace {trace['trace_id']} for {trace['operation']} ({trace['service']}) with start time {start_time} and end time {end_time}")
        
        trace_perf_data = get_perf_metrics_for_trace(processed_perf_df, start_time, end_time)
        if trace_perf_data.empty:
            print(f"No perf data found for trace {trace['trace_id']}")
            continue

        metrics = calculate_perf_metrics(trace_perf_data)
        plot_path = plot_trace_perf_metrics(trace, trace_perf_data, output_dir)
        
        results.append({
            'trace_id': trace['trace_id'],
            'span_id': trace['span_id'],
            'operation_name': trace['operation'],
            'service_name': trace['service'],
            'duration_us': trace['duration'],
            'start_time_us': trace['start_time'],
            'end_time_us': trace['end_time'],
            'llc_loads': metrics['llc_loads_delta'],
            'llc_misses': metrics['llc_misses_delta'],
            'instructions': metrics['instructions_delta'],
            'llc_miss_rate': metrics['llc_miss_rate'],
            'plot_path': plot_path
        })
    
    return pd.DataFrame(results)

def main() -> None:
    args: argparse.Namespace = parse_arguments()
    test_name: str = args.test_name.replace(" ", "_")
    service_name_for_traces: str = args.service_name_for_traces
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    samples_per_operation: int = args.samples_per_operation
    plot_dir: str = args.plot_dir
    
    print("Plotting Jaeger trace data")
    print(f"Test Name: {test_name}")
    print(f"Service Name for Traces: {service_name_for_traces}")
    print(f"Container Name: {container_name}")
    print(f"Config: {config}")
    print(f"Data Directory: {data_dir}")
    print(f"Samples per Operation: {samples_per_operation}")
    print(f"Plot Directory: {plot_dir}")
    
    container_jaeger_traces_df: pd.DataFrame = load_traces_data(
        data_dir, service_name_for_traces, test_name, config, container_name)
    perf_df: pd.DataFrame = load_perf_data(data_dir)
    
    print(f"Loaded {len(container_jaeger_traces_df)} traces and {len(perf_df)} perf data points")
    
    results_df = analyze_traces_with_perf_data(
        container_jaeger_traces_df, 
        perf_df, 
        samples_per_operation,
        plot_dir
    )

    # TODO: perf graph with start and end lines for traces
    
    if not results_df.empty:
        results_file = os.path.join(data_dir, "data", "trace_perf_analysis.csv")
        results_df.to_csv(results_file, index=False)
        print(f"Analysis complete. Results saved to {results_file}")
        
        summary_file = os.path.join(data_dir, "data", "trace_perf_summary_report.csv")
        summary_df = results_df.groupby('operation_name').agg({
            'duration_us': ['mean', 'min', 'max', 'count'],
            'llc_loads': ['mean', 'min', 'max', 'sum'],
            'llc_misses': ['mean', 'min', 'max', 'sum'],
            'instructions': ['mean', 'min', 'max', 'sum'],
            'llc_miss_rate': ['mean', 'min', 'max']
        })
        summary_df.to_csv(summary_file)
        print(f"Summary report saved to {summary_file}")
    else:
        print("No results generated. Check your input data.")

if __name__ == "__main__":
    main()