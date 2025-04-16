import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Non-Idle median trace duration VS cache partitions for each container.")
    parser.add_argument("--data-dir", type=str, required=True, help="Directory containing the input CSV files.")
    parser.add_argument("--plot-dir", type=str, required=True, help="Directory to save the output plots.")
    return parser.parse_args()

def plot_non_idle_durations(non_idle_durations_df: pd.DataFrame, container_name: str, plot_dir: str) -> None:
    non_idle_durations_df["cache_partitions"] = non_idle_durations_df["cache_partitions"].astype(int)
    non_idle_durations_df = non_idle_durations_df.sort_values(by="cache_partitions")
    cache_partitions = non_idle_durations_df["cache_partitions"].unique()
    
    plt.figure(figsize=(12, 8))
    positions = np.array(cache_partitions)
    violins = plt.violinplot(
        [non_idle_durations_df[non_idle_durations_df["cache_partitions"] == cp]["non_idle_duration"].values for cp in cache_partitions],
        positions=positions,
        widths=0.8,
        showmeans=False,
        showmedians=False,
        showextrema=False
    )
    for pc in violins['bodies']:
        pc.set_facecolor('lightblue')
        pc.set_edgecolor('none')
        pc.set_alpha(0.6)
    median_values = []
    worst_case_values = []
    for cp in cache_partitions:
        partition_data = non_idle_durations_df[non_idle_durations_df["cache_partitions"] == cp]["non_idle_duration"]
        median_values.append(partition_data.median())
        worst_case_values.append(partition_data.max())
    plt.plot(positions, median_values, 'bo-', linewidth=2, markersize=8, label="Median Non-Idle Duration")
    plt.plot(positions, worst_case_values, 'ro--', linewidth=2, markersize=8, label="Worst Case Non-Idle Duration")
    plt.xlabel("Num Cache Partitions", fontsize=12)
    plt.ylabel("Non-Idle Trace Duration", fontsize=12)
    plt.title(f"{container_name}\nNon-Idle Trace Duration Distribution VS Cache Partitions", fontsize=14)
    plt.legend(fontsize=10)
    plt.grid(alpha=0.3)
    plt.xticks(positions)
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, f"{container_name}_non_idle_duration.png"), dpi=300)
    plt.close()

def main():
    args: argparse.Namespace = parse_arguments()
    data_dir: str = args.data_dir
    plot_dir: str = args.plot_dir
    
    os.makedirs(plot_dir, exist_ok=True)
    # loop over all csv files in the input directory
    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            container_name = filename.split(".")[0]
            filepath = os.path.join(data_dir, filename)
            non_idle_durations_df: pd.DataFrame = pd.read_csv(filepath)
            plot_non_idle_durations(non_idle_durations_df, container_name, plot_dir)
            print(f"Processed {filename} and saved plot to {plot_dir}")

if __name__ == "__main__":
    main()