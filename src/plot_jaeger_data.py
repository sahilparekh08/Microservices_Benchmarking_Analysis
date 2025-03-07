import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import math
import os
import numpy as np

def parse_arguments():
    parser = argparse.ArgumentParser(description="Plot Jaeger trace data for a given service.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Test configuration")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    
    return parser.parse_args()

def load_data(data_dir, service_name_for_traces, test_name, config, container_name):
    jaeger_traces_csv_file_path = os.path.join(data_dir, "data", 
                                               f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    jaeger_traces_df = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    container_stats = container_jaeger_traces_df.groupby('service')['non_idle_execution_time'].describe(
        percentiles=[.25, .5, .75])
    unique_services = container_jaeger_traces_df['service'].unique()
    
    return container_jaeger_traces_df, container_stats, unique_services

def create_stats_text_box(ax, service, stats, position):
    stats_text = (f"{service}\n"
                 f"Median: {stats['50%']:.2f}\n"
                 f"25th: {stats['25%']:.2f}\n"
                 f"75th: {stats['75%']:.2f}")
    props = dict(boxstyle='round', facecolor='white', alpha=0.7, edgecolor='gray')
    ax.text(position[0], position[1], stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', bbox=props)

def plot_histogram(ax, data, service, stats, container_name):
    sns.set_style("whitegrid")
    
    sns.histplot(data, kde=True, ax=ax, color='steelblue', alpha=0.7)
    
    ax.axvline(stats['50%'], color='red', linestyle='--', linewidth=1.5, label='Median')
    ax.axvline(stats['25%'], color='green', linestyle='--', linewidth=1.5, label='25th')
    ax.axvline(stats['75%'], color='blue', linestyle='--', linewidth=1.5, label='75th')
    
    ax.set_title(f'{container_name} - {service}', fontsize=12, fontweight='bold', pad=10)
    ax.set_xlabel('Non-Idle Execution Time', fontsize=10)
    ax.set_ylabel('Frequency', fontsize=10)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=3, frameon=True, fontsize=8)

    create_stats_text_box(ax, service, stats, (0.65, 0.95))
    
    ax.tick_params(axis='both', labelsize=8)
    ax.grid(True, linestyle='--', alpha=0.7)

def main():
    args = parse_arguments()

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

    container_jaeger_traces_df, container_stats, unique_services = load_data(
        data_dir, service_name_for_traces, test_name, config, container_name)

    print(f"Plotting Jaeger trace data for container [{container_name}] which covers the following services [{', '.join(unique_services)}]")
    print(f"Total traces: {len(container_jaeger_traces_df)}")

    num_plots = len(container_stats)
    plots_per_file = 4
    num_files = math.ceil(num_plots / plots_per_file)

    for file_idx in range(num_files):
        remaining_plots = min(plots_per_file, num_plots - file_idx * plots_per_file)
        rows = math.ceil(remaining_plots / 2)
        cols = min(2, remaining_plots)

        plt.figure(figsize=(12, 10))
        fig, axs = plt.subplots(rows, cols, figsize=(12, 10))
        plt.style.use('ggplot')
        
        if rows == 1 and cols == 1:
            axs = np.array([[axs]])
        elif rows == 1:
            axs = np.expand_dims(axs, axis=0)
        elif cols == 1:
            axs = np.expand_dims(axs, axis=1)

        fig.suptitle(
            f"Non-Idle Execution Time - {container_name}\nTest: {test_name} | Config: {config} | Page {file_idx + 1}/{num_files}", 
            fontsize=14, 
            y=0.98,
            fontweight='bold'
        )

        plot_count = 0
        for idx, (service, stats) in enumerate(container_stats.iterrows()):
            if idx < file_idx * plots_per_file or idx >= (file_idx + 1) * plots_per_file:
                continue
            row = plot_count // cols
            col = plot_count % cols
            ax = axs[row, col]
            service_data = container_jaeger_traces_df[
                container_jaeger_traces_df['service'] == service]['non_idle_execution_time']
            plot_histogram(ax, service_data, service, stats, container_name)
            plot_count += 1

        for i in range(plot_count, rows * cols):
            axs[i // cols, i % cols].axis('off')

        plt.tight_layout()
        plt.subplots_adjust(top=0.9, hspace=0.4, wspace=0.3)
        
        output_file_path = os.path.join(
            data_dir, 
            "plots", 
            f"{container_name}_{test_name}_{config}_non_idle_exec_time_dist_{file_idx}.png"
        )
        
        plt.savefig(output_file_path, bbox_inches='tight', dpi=300)
        plt.close(fig)

        print(f'Plots saved to {output_file_path}')

    print("Done plotting Jaeger trace data")

if __name__ == "__main__":
    main()