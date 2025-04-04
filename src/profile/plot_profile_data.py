import matplotlib.pyplot as plt
import pandas as pd
import argparse
import numpy as np
from typing import Tuple, Dict
from plot_profile_utils import load_profile_data, get_processed_df

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot LLC Load, Miss, and Instruction Frequencies over Time.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Configuration name")
    parser.add_argument("--data-dir", type=str, required=True, help="Directory containing LLC data")
    parser.add_argument("--plot-dir", type=str, required=True, help="Directory to save plots")
    return parser.parse_args()

def calculate_percentiles(df: pd.DataFrame, column: str) -> Tuple[pd.DataFrame, float, float, float, float]:
    data: pd.DataFrame = get_processed_df(df, column, True)
    data[column] = data[column].replace(0, np.nan)
    data = data.dropna()
    median: float = float(np.median(data[column]))
    p25: float = float(np.percentile(data[column], 25))
    p75: float = float(np.percentile(data[column], 75))
    p99: float = float(np.percentile(data[column], 99))
    print(f"{column} Median: {median:.2f} | 25th: {p25:.2f} | 75th: {p75:.2f} | 99th: {p99:.2f}")
    return data, median, p25, p75, p99

def plot_data_with_fixed_x_axis(
    axes: plt.Axes,
    data: pd.DataFrame,
    label: str,
    color: str,
    position: int,
    x_min: int,
    x_max: int
) -> None:
    axes[position].scatter(data["Time"], data[label], label=label, color=color, marker="o", s=10)  
    axes[position].set_xlim(x_min, x_max)

def plot_data(
    axes: plt.Axes,
    data: pd.DataFrame,
    median: float,
    p25: float,
    p75: float,
    p99: float,
    label: str,
    color: str,
    position: int,
    title: str,
    p99_cutoff_percent: float = 0.05
) -> None:
    axes[position].scatter(data["Time"], data[label], label=label, color=color, marker="o", s=10)  
    axes[position].axhline(median, color=color, linestyle="--", label=f"{title} Median", alpha=0.7)
    axes[position].axhline(p25, color=color, linestyle=":", label=f"{title} 25th", alpha=0.5)
    axes[position].axhline(p75, color=color, linestyle=":", label=f"{title} 75th", alpha=0.5)
    axes[position].axhline(p99, color=color, linestyle=":", label=f"{title} 99th", alpha=0.5)
    
    above_99: int = len(data[data[label] > p99])
    y_lim_max: float = data[label].max() * 1.1
    if above_99 > 0 and above_99 < len(data) * p99_cutoff_percent:
        y_lim_max = max(y_lim_max, p99 * 1.1)
    axes[position].set_ylim(0, y_lim_max)

def add_text_box(
    axes: plt.Axes, 
    idx: int, 
    median: float, 
    p25: float, 
    p75: float, 
    p99: float, 
    label: str, 
    color: str, 
    y_offset: float = 0
) -> None:
    text: str = f'{label}\nMedian: {median:.2f}\n25th: {p25:.2f}\n75th: {p75:.2f}\n99th: {p99:.2f}'
    bbox_props: dict = {
        "boxstyle": "round,pad=0.5",
        "facecolor": "white",
        "alpha": 0.8,
        "edgecolor": color,
        "linewidth": 2
    }
    axes[idx].annotate(
        text,
        xy=(1.02, 0.95 - y_offset),
        xycoords='axes fraction',
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='left',
        bbox=bbox_props
    )

def save_plot(fig: plt.Figure, output_file_path: str) -> None:
    fig.tight_layout()
    plt.savefig(output_file_path, bbox_inches='tight', dpi=300)
    print(f"Plot saved as {output_file_path}")

def main() -> None:
    args: argparse.Namespace = parse_arguments()

    test_name: str = args.test_name.replace(" ", "_")
    container_name: str = args.container_name
    configs: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    plot_dir: str = args.plot_dir

    print("Plotting LLC Load, Miss, and Instruction Frequencies over Time")
    print(f"Test Name: {test_name}")
    print(f"Container Name: {container_name}")
    print(f"Config: {configs}")
    print(f"Data Directory: {data_dir}")

    cores_to_perf_df: Dict[str, pd.DataFrame] = load_profile_data(data_dir)

    if len(cores_to_perf_df) == 1:
        core: str = list(cores_to_perf_df.keys())[0]
        perf_df: pd.DataFrame = cores_to_perf_df[core]
        output_file_path: str = f"{plot_dir}/{test_name}_{container_name}_core_{core}_{configs}.png"
        print(f"Output File Path: {output_file_path}")
        
        loads, loads_median, loads_25th, loads_75th, loads_99th = calculate_percentiles(perf_df, "LLC-loads")
        misses, misses_median, misses_25th, misses_75th, misses_99th = calculate_percentiles(perf_df, "LLC-misses")
        instructions, instructions_median, instructions_25th, instructions_75th, instructions_99th = calculate_percentiles(perf_df, "Instructions")

        loads["LLC-loads"] = loads["LLC-loads"].astype(int)
        misses["LLC-misses"] = misses["LLC-misses"].astype(int)
        instructions["Instructions"] = instructions["Instructions"].astype(int)
        loads["Time"] = loads["Time"].astype(int)
        misses["Time"] = misses["Time"].astype(int)
        instructions["Time"] = instructions["Time"].astype(int)
        loads["LLC-loads"] = loads["LLC-loads"].replace(0, np.nan)
        misses["LLC-misses"] = misses["LLC-misses"].replace(0, np.nan)
        instructions["Instructions"] = instructions["Instructions"].replace(0, np.nan)
        loads = loads.dropna()
        misses = misses.dropna()
        instructions = instructions.dropna()
        loads = loads.sort_values(by="Time")
        misses = misses.sort_values(by="Time")
        instructions = instructions.sort_values(by="Time")

        plt.style.use('ggplot')
        
        fig, axes = plt.subplots(2, 1, figsize=(12, 12))

        plot_data(axes, loads, loads_median, loads_25th, loads_75th, loads_99th, "LLC-loads", "blue", 0, "Loads")
        plot_data(axes, misses, misses_median, misses_25th, misses_75th, misses_99th, "LLC-misses", "red", 0, "Misses")
        plot_data(axes, instructions, instructions_median, instructions_25th, instructions_75th, instructions_99th, "Instructions", "green", 1, "Instr", 0.1)

        add_text_box(axes, 0, loads_median, loads_25th, loads_75th, loads_99th, "LLC-loads", "blue", 0)
        add_text_box(axes, 0, misses_median, misses_25th, misses_75th, misses_99th, "LLC-misses", "red", 0.25)
        add_text_box(axes, 1, instructions_median, instructions_25th, instructions_75th, instructions_99th, "Instructions", "green", 0)

        fig.suptitle(f"CORE: {core} | TEST: {test_name} | SERVICE: {container_name} | CONFIGS: {configs}", fontsize=14, fontweight='bold', y=0.98)
        save_plot(fig, output_file_path)
    else:
        llc_loads: pd.DataFrame = pd.DataFrame()
        llc_misses: pd.DataFrame = pd.DataFrame()
        core_to_instructions: Dict[str, pd.DataFrame] = {}
    
        for core, perf_df in cores_to_perf_df.items():
            loads = get_processed_df(perf_df, "LLC-loads", True)
            misses = get_processed_df(perf_df, "LLC-misses", True)
            instructions = get_processed_df(perf_df, "Instructions", False)

            loads["LLC-loads"] = loads["LLC-loads"].replace(0, np.nan)
            misses["LLC-misses"] = misses["LLC-misses"].replace(0, np.nan)
            instructions["Instructions"] = instructions["Instructions"].replace(0, np.nan)
            loads = loads.dropna()
            misses = misses.dropna()
            instructions = instructions.dropna()

            llc_loads = pd.concat([llc_loads, loads], axis=0)
            llc_misses = pd.concat([llc_misses, misses], axis=0)
            core_to_instructions[core] = instructions

        llc_loads = llc_loads.groupby("Time").sum().reset_index()
        llc_misses = llc_misses.groupby("Time").sum().reset_index()

        # Plot LLC loads and misses
        loads, loads_median, loads_25th, loads_75th, loads_99th = calculate_percentiles(llc_loads, "LLC-loads")
        misses, misses_median, misses_25th, misses_75th, misses_99th = calculate_percentiles(llc_misses, "LLC-misses")

        loads["LLC-loads"] = loads["LLC-loads"].astype(int)
        misses["LLC-misses"] = misses["LLC-misses"].astype(int)
        loads["Time"] = loads["Time"].astype(int)
        misses["Time"] = misses["Time"].astype(int)
        loads["LLC-loads"] = loads["LLC-loads"].replace(0, np.nan)
        misses["LLC-misses"] = misses["LLC-misses"].replace(0, np.nan)
        loads = loads.dropna()
        misses = misses.dropna()
        loads = loads.sort_values(by="Time")
        misses = misses.sort_values(by="Time")

        plt.style.use('ggplot')
        fig, axes = plt.subplots(1, 1, figsize=(12, 6))
        plot_data(axes, loads, loads_median, loads_25th, loads_75th, loads_99th, "LLC-loads", "blue", 0, "Loads")
        plot_data(axes, misses, misses_median, misses_25th, misses_75th, misses_99th, "LLC-misses", "red", 0, "Misses")
        add_text_box(axes, 0, loads_median, loads_25th, loads_75th, loads_99th, "LLC-loads", "blue", 0)
        add_text_box(axes, 0, misses_median, misses_25th, misses_75th, misses_99th, "LLC-misses", "red", 0.25)
        fig.suptitle(f"LLC Loads and Misses\nTEST: {test_name} | SERVICE: {container_name} | CONFIGS: {configs}", fontsize=14, fontweight='bold', y=0.98)
        output_file_path: str = f"{plot_dir}/{test_name}_{container_name}_llc_data_all_cores_{configs}.png"
        save_plot(fig, output_file_path)

        # Plot Instructions per core
        fig, axes = plt.subplots(len(core_to_instructions), 1, figsize=(12, 6 * len(core_to_instructions)))
        min_time = min([df["Time"].min() for df in core_to_instructions.values()])
        max_time = max([df["Time"].max() for df in core_to_instructions.values()])

        for idx, (core, instructions) in enumerate(core_to_instructions.items()):
            plot_data_with_fixed_x_axis(axes, instructions, "Instructions", "green", idx, min_time, max_time)
            axes[idx].set_title(f"Core: {core}")

        fig.suptitle(f"Instructions\nTEST: {test_name} | SERVICE: {container_name} | CONFIGS: {configs}", fontsize=14, fontweight='bold', y=0.98)
        output_file_path: str = f"{plot_dir}/{test_name}_{container_name}_instructions_all_cores_{configs}.png"
        save_plot(fig, output_file_path)

if __name__ == "__main__":
    main()