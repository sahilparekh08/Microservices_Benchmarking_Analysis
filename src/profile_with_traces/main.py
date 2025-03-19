"""
Main entry point for profile with traces analysis.
"""

import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd

from .utils.constants import DEFAULT_SERVICE_NAME
from .data_processing.data_loader import load_traces_data, load_perf_data
from .data_processing.trace_processor import get_highest_resource_usage_traces, get_non_overlapping_longest_durations
from .visualization.plotting import (
    plot_aligned_median_resource_usage,
    plot_traces_start_end_times_and_perf_data,
    plot_profile_with_traces
)

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
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

def main() -> None:
    """Main entry point."""
    args: argparse.Namespace = parse_arguments()
    test_name: str = args.test_name.replace(" ", "_")
    service_name_for_traces: str = args.service_name_for_traces
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    samples: int = args.samples
    plot_dir: str = args.plot_dir
    
    if args.default_service_name:
        global DEFAULT_SERVICE_NAME
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