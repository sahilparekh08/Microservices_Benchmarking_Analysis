import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import math
import os
import numpy as np
from typing import Tuple

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Jaeger trace data for a given service.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Test configuration")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--plot-dir", type=str, required=True, help="Plot directory")
    
    return parser.parse_args()

def load_data(
        data_dir: str,
        service_name_for_traces: str,
        test_name: str,
        config: str,
        container_name: str
        ) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    jaeger_traces_csv_file_path: str = os.path.join(data_dir, "data", 
                                                    f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    jaeger_traces_df: pd.DataFrame = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df: pd.DataFrame = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    per_service_operation_stats: pd.DataFrame = (
        container_jaeger_traces_df
        .groupby(['service', 'operation'])['non_idle_execution_time']
        .describe(percentiles=[.25, .5, .75])
        .reset_index()
        .rename(columns={'50%': 'median', '25%': 'q25', '75%': 'q75'})
    )
    unique_services: np.ndarray = container_jaeger_traces_df['service'].unique()
    return container_jaeger_traces_df, per_service_operation_stats, unique_services

def create_stats_text_box(
        ax: plt.Axes,
        operation: str,
        stats: pd.Series,
        position: Tuple[float, float]
        ) -> None:
    stats_text: str = (f"{operation}\n"
                   f"Median: {stats['median']:.2f}\n"
                   f"25th: {stats['q25']:.2f}\n"
                   f"75th: {stats['q75']:.2f}")
    props: dict = dict(boxstyle='round', facecolor='white', alpha=0.7, edgecolor='gray')
    ax.text(position[0], position[1], stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', bbox=props)

def plot_histogram(
        ax: plt.Axes,
        data: pd.Series,
        operation: str,
        stats: pd.Series,
        x_min: float,
        x_max: float,
        y_max: float
        ) -> None:
    sns.set_style("whitegrid")
    
    sns.histplot(data, kde=True, ax=ax, color='steelblue', alpha=0.7)
    
    ax.axvline(stats['median'], color='red', linestyle='--', linewidth=1.5)
    ax.axvline(stats['q25'], color='green', linestyle='--', linewidth=1.5)
    ax.axvline(stats['q75'], color='blue', linestyle='--', linewidth=1.5)
    
    ax.set_title(f'{operation}', fontsize=12, fontweight='bold', pad=10)
    ax.set_xlabel('Non-Idle Execution Time', fontsize=10)
    ax.set_ylabel('Frequency', fontsize=10)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, y_max)
    
    create_stats_text_box(ax, operation, stats, (0.65, 0.95))
    
    ax.tick_params(axis='both', labelsize=8)
    ax.grid(True, linestyle='--', alpha=0.7)

def plot_jaeger_service_data(
        container_jaeger_traces_df: pd.DataFrame, 
        per_service_operation_stats: pd.DataFrame,
        unique_services: np.ndarray,
        data_dir: str,
        plot_dir: str,
        container_name: str, 
        test_name: str, 
        config: str
) -> None:
    for service in unique_services:
        service_data_df: pd.DataFrame = container_jaeger_traces_df[container_jaeger_traces_df['service'] == service]
        service_stats_df: pd.DataFrame = per_service_operation_stats[per_service_operation_stats['service'] == service]

        histograms = []
        for operation, stats in service_stats_df.groupby('operation'):
            operation_data = service_data_df[service_data_df['operation'] == operation]['non_idle_execution_time']
            hist, _ = np.histogram(operation_data, bins='auto')
            histograms.append(hist)
        
        x_min = service_data_df['non_idle_execution_time'].min()
        x_max = service_data_df['non_idle_execution_time'].max() * 1.05
        
        y_max = max([h.max() for h in histograms]) * 1.1 

        num_operations: int = len(service_stats_df)
        plots_per_row: int = 4
        rows: int = math.ceil(num_operations / plots_per_row)

        fig, axs = plt.subplots(rows, plots_per_row, figsize=(12, 5 * rows))
        plt.style.use('ggplot')
        axs = np.array(axs).reshape(rows, plots_per_row)

        fig.suptitle(
            f"Non-Idle Execution Time - {container_name}\nService: {service} | Test: {test_name} | Config: {config}", 
            fontsize=14, 
            y=0.98,
            fontweight='bold'
        )

        plot_count: int = 0
        for operation, stats in service_stats_df.groupby('operation'):
            row: int = plot_count // plots_per_row
            col: int = plot_count % plots_per_row
            ax: plt.Axes = axs[row, col]

            operation_data: pd.Series = service_data_df[service_data_df['operation'] == operation]['non_idle_execution_time']
            plot_histogram(ax, operation_data, str(operation), stats.iloc[0], x_min, x_max, y_max)
            plot_count += 1

        for i in range(plot_count, rows * plots_per_row):
            axs[i // plots_per_row, i % plots_per_row].axis('off')

        plt.tight_layout()
        plt.subplots_adjust(top=0.9, hspace=0.4, wspace=0.3)

        output_file_path: str = os.path.join(
            plot_dir, f"{container_name}_{test_name}_{config}_service_{service}_exec_time_dist.png"
        )

        plt.savefig(output_file_path, bbox_inches='tight', dpi=300)
        plt.close(fig)

        print(f'Plot saved: {output_file_path}')

    print("Done plotting Jaeger trace data")

def main() -> None:
    args: argparse.Namespace = parse_arguments()

    test_name: str = args.test_name.replace(" ", "_")
    service_name_for_traces: str = args.service_name_for_traces
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    plot_dir: str = args.plot_dir

    print("Plotting Jaeger trace data")
    print(f"Test Name: {test_name}")
    print(f"Service Name for Traces: {service_name_for_traces}")
    print(f"Container Name: {container_name}")
    print(f"Config: {config}")
    print(f"Data Directory: {data_dir}")
    print(f"Plot Directory: {plot_dir}")

    container_jaeger_traces_df, per_service_operation_stats, unique_services = load_data(
        data_dir, service_name_for_traces, test_name, config, container_name)

    print(f"Plotting Jaeger trace data for container [{container_name}] which covers the following services [{', '.join(unique_services)}]")
    print(f"Total traces: {len(container_jaeger_traces_df)}")
    
    plot_jaeger_service_data(container_jaeger_traces_df, per_service_operation_stats, unique_services, data_dir, plot_dir, container_name, test_name, config)

if __name__ == "__main__":
    main()