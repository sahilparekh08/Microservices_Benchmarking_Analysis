import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import math
import os
import numpy as np

parser = argparse.ArgumentParser(description="Plot Jaeger trace data for a given service.")
parser.add_argument("--test-name", type=str, required=True, help="Test name")
parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
parser.add_argument("--container-name", type=str, required=True, help="Service name")
parser.add_argument("--config", type=str, required=True, help="Test configuration")
parser.add_argument("--data-dir", type=str, required=True, help="Data directory")

args = parser.parse_args()

test_name = args.test_name.replace(" ", "_")
service_name_for_traces = args.service_name_for_traces
container_name = args.container_name
config = args.config.replace(" ", "_")
data_dir = args.data_dir

print("Plotting Jaeger trace data")
print(f"Test Name: {test_name}")
print(f"Service Name for Traces: {service_name_for_traces}")
print(f"Container Name: {container_name}")
print(f"Config: {config}")
print(f"Data Directory: {data_dir}")

jaeger_traces_csv_file_path = data_dir + "/data/" + service_name_for_traces + "_" + test_name + "_" + config + "_traces_data.csv"

jaeger_traces_df = pd.read_csv(jaeger_traces_csv_file_path)
container_jaeger_traces_df = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
unique_services = container_jaeger_traces_df['service'].unique()

print(f"Plotting Jaeger trace data for container [{container_name}] which covers the following services [{', '.join(unique_services)}]")
print(f"Total traces: {len(container_jaeger_traces_df)}")

container_stats = container_jaeger_traces_df.groupby('service')['non_idle_execution_time'].describe(percentiles=[.25, .5, .75])

num_plots = len(container_stats)
num_files = math.ceil(num_plots / 6)

for file_idx in range(num_files):
    remaining_plots = min(6, num_plots - file_idx * 6)
    rows = math.ceil(remaining_plots / 3)
    cols = min(3, remaining_plots)
    fig, axs = plt.subplots(rows, cols, figsize=(20, 10))
    
    if rows == 1 and cols == 1:
        axs = np.array([[axs]])
    elif rows == 1:
        axs = np.expand_dims(axs, axis=0)
    elif cols == 1:
        axs = np.expand_dims(axs, axis=1)

    fig.suptitle(f"Jaeger Trace Data for Container [{container_name}] - File [{file_idx + 1}/{num_files}]", fontsize=16, y=1.05)

    plot_count = 0

    for idx, (service, stats) in enumerate(container_stats.iterrows()):
        if idx < file_idx * 6 or idx >= (file_idx + 1) * 6:
            continue

        row = plot_count // cols
        col = plot_count % cols
        ax = axs[row, col]

        sns.histplot(container_jaeger_traces_df[container_jaeger_traces_df['service'] == service]['non_idle_execution_time'], kde=True, ax=ax)
        ax.set_title(f'{container_name} - {service}', fontsize=14)
        ax.set_xlabel('Non-Idle Execution Time', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.axvline(stats['50%'], color='r', linestyle='--', label='Median')
        ax.axvline(stats['25%'], color='g', linestyle='--', label='25th Percentile')
        ax.axvline(stats['75%'], color='b', linestyle='--', label='75th Percentile')

        ax.text(0.95, 0.90, f'Median: {stats["50%"]:.2f}', ha='right', va='center', transform=ax.transAxes, fontsize=10, color='r')
        ax.text(0.95, 0.85, f'25th Percentile: {stats["25%"]:.2f}', ha='right', va='center', transform=ax.transAxes, fontsize=10, color='g')
        ax.text(0.95, 0.80, f'75th Percentile: {stats["75%"]:.2f}', ha='right', va='center', transform=ax.transAxes, fontsize=10, color='b')

        ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=10)
        ax.grid(True)

        plot_count += 1

    if rows == 1:
        for i in range(plot_count, cols):
            axs[0, i].axis('off')
    else:
        for i in range(plot_count, rows * cols):
            axs[i // cols, i % cols].axis('off')

    plt.tight_layout(rect=[0, 0, 0.9, 1])
    output_file_path = os.path.join(data_dir, "plots", f"{container_name}_{test_name}_{config}_non_idle_exec_time_dist_{file_idx}.png")
    plt.savefig(output_file_path, bbox_inches='tight')
    plt.close(fig)

    print(f'Plots saved to {output_file_path}')

print("Done plotting Jaeger trace data")
