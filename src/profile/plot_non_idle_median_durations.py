import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Non-Idle median trace duration VS cache partitions for each container.")
    parser.add_argument("--data-dir", type=str, required=True, help="Directory containing the input CSV files.")
    parser.add_argument("--plot-dir", type=str, required=True, help="Directory to save the output plots.")
    return parser.parse_args()

def main():
    args: argparse.Namespace = parse_arguments()
    data_dir: str = args.data_dir
    plot_dir: str = args.plot_dir

    # loop over all csv files in the input directory
    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            container_name = filename.split(".")[0]
            filepath = os.path.join(data_dir, filename)
            non_idle_median_durations_df: pd.DataFrame = pd.read_csv(filepath)
            non_idle_median_durations_df["cache_partitions"] = non_idle_median_durations_df["cache_partitions"].astype(int)
            non_idle_median_durations_df = non_idle_median_durations_df.sort_values(by="cache_partitions")

            # x axis is cache partitions, y axis is non-idle median trace duration
            plt.figure()
            plt.plot(non_idle_median_durations_df["cache_partitions"], non_idle_median_durations_df["non_idle_median_duration"])
            plt.xlabel("Num Cache Partitions")
            plt.ylabel("Non-Idle Median Trace Duration")
            plt.title(f"Non-Idle Median Trace Duration VS Cache Partitions for {container_name}")
            plt.grid()
            plt.savefig(os.path.join(plot_dir, f"{container_name}_non_idle_median_duration.png"))
            plt.close()

if __name__ == "__main__":
    main()