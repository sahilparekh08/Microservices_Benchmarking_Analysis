import argparse
import os
import pandas as pd
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import numpy as np

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Jaeger trace data for a given service.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Test configuration")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--samples", type=int, default=3, help="Number of samples per operation")
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
    llc_data_file: str = f"{data_dir}/data/profile_data.csv"
    df: pd.DataFrame = pd.read_csv(llc_data_file, sep=",")
    return df

def get_samples(traces_df: pd.DataFrame, profile_df: pd.DataFrame, num_samples: int) -> pd.DataFrame:
    sampled_traces = pd.DataFrame()
    trace_ids = list(traces_df['trace_id'].unique())
    random.shuffle(trace_ids)

    min_perf_time = profile_df['Time'].min()
    max_perf_time = profile_df['Time'].max()
    
    for trace_id in trace_ids:
        trace_sample = traces_df[traces_df['trace_id'] == trace_id]
        trace_start = trace_sample['start_time'].min()
        trace_end = trace_sample['end_time'].max()
        
        if trace_end < min_perf_time or trace_start > max_perf_time:
            continue
        if trace_start < min_perf_time or trace_end > max_perf_time:
            continue

        sampled_traces = pd.concat([sampled_traces, trace_sample])
        if len(sampled_traces) == num_samples:
            break
    
    return sampled_traces

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
    config: str
) -> None:
    profile_df["Time"] = profile_df["Time"].astype(float)
    transformed_traces_df["start_time"] = transformed_traces_df["start_time"].astype(float)
    transformed_traces_df["end_time"] = transformed_traces_df["end_time"].astype(float)
    num_plots = 0

    print(f"Trying to plot [{len(transformed_traces_df)}] traces")

    for _, trace in transformed_traces_df.iterrows():
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

        fig, axs = plt.subplots(2, 1, figsize=(15, 10))

        zoom_margin = 0.001
        zoomed_plot_profile_df = profile_df[
            (profile_df["Time"] >= trace_start - zoom_margin) & 
            (profile_df["Time"] <= trace_end + zoom_margin)
        ]

        zoomed_plot_profile_df["LLC-loads"] = zoomed_plot_profile_df["LLC-loads"].astype(float)
        zoomed_plot_profile_df["LLC-misses"] = zoomed_plot_profile_df["LLC-misses"].astype(float)
        zoomed_plot_profile_df["Instructions"] = zoomed_plot_profile_df["Instructions"].astype(float)

        zoomed_plot_profile_df["LLC-loads"] = zoomed_plot_profile_df["LLC-loads"].replace(0, np.nan)
        zoomed_plot_profile_df["LLC-misses"] = zoomed_plot_profile_df["LLC-misses"].replace(0, np.nan)
        zoomed_plot_profile_df["Instructions"] = zoomed_plot_profile_df["Instructions"].replace(0, np.nan)

        zoomed_plot_profile_df = zoomed_plot_profile_df.dropna(subset=["LLC-loads", "LLC-misses", "Instructions"])
        zoomed_plot_profile_df = zoomed_plot_profile_df.sort_values(by="Time")
        zoomed_plot_profile_df['Time'] = zoomed_plot_profile_df['Time'].astype(int)
        zoomed_plot_profile_df['Time'] = zoomed_plot_profile_df['Time'] - zoomed_plot_profile_df['Time'].min()

        fig, axs = plt.subplots(2, 1, figsize=(15, 10))

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

        print(f"Plots saved to {output_dir}/trace_{num_plots}_perf_plot.png and {output_dir}/trace_{num_plots}_zoomed_perf_plot.png")

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
    args: argparse.Namespace = parse_arguments()
    test_name: str = args.test_name.replace(" ", "_")
    service_name_for_traces: str = args.service_name_for_traces
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    samples: int = args.samples
    plot_dir: str = args.plot_dir
    os.makedirs(plot_dir, exist_ok=True)
    
    container_jaeger_traces_df: pd.DataFrame = load_traces_data(
        data_dir, service_name_for_traces, test_name, config, container_name)
    profile_df: pd.DataFrame = load_perf_data(data_dir)

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

    plot_traces_start_end_times_and_perf_data(
        container_jaeger_traces_df,
        profile_df,
        plot_dir
    )

    transformed_traces_df = get_transformed_traces_df(container_jaeger_traces_df)
    plot_profile_with_traces(transformed_traces_df, profile_df, plot_dir, samples, config)
    
    print("Plot generation complete.")

if __name__ == "__main__":
    main()
