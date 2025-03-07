import matplotlib.pyplot as plt
import pandas as pd
import argparse
import numpy as np
from typing import Tuple

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot LLC Load, Miss, and Instruction Frequencies over Time.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Configuration name")
    parser.add_argument("--data-dir", type=str, required=True, help="Directory containing LLC data")
    return parser.parse_args()

def load_data(data_dir: str) -> pd.DataFrame:
    llc_data_file: str = f"{data_dir}/data/llc_data.csv"
    df: pd.DataFrame = pd.read_csv(llc_data_file, sep=",")
    df["Time"] = df["Time"] - df["Time"].min()
    return df

def calculate_percentiles(df: pd.DataFrame, data_type: str) -> Tuple[pd.DataFrame, float, float, float]:
    data: pd.DataFrame = df[df["Type"] == data_type]
    median: float = float(np.median(data["Frequency"]))
    p25: float = float(np.percentile(data["Frequency"], 25))
    p75: float = float(np.percentile(data["Frequency"], 75))
    return data, median, p25, p75

def plot_data(
    axes: plt.Axes,
    data: pd.DataFrame,
    median: float,
    p25: float,
    p75: float,
    label: str,
    color: str,
    linestyle: str,
    position: int,
    title: str
) -> None:
    axes[position].plot(data["Time"], data["Frequency"], label=label, color=color, marker="o", linestyle=linestyle, markersize=4)
    axes[position].axhline(median, color=color, linestyle="--", label=f"{title} Median", alpha=0.7)
    axes[position].axhline(p25, color=color, linestyle=":", label=f"{title} 25th", alpha=0.5)
    axes[position].axhline(p75, color=color, linestyle=":", label=f"{title} 75th", alpha=0.5)

def add_text_box(
    axes: plt.Axes, 
    idx: int, 
    median: float, 
    p25: float, 
    p75: float, 
    label: str, 
    color: str, 
    y_offset: float = 0
) -> None:
    text: str = f'{label}\nMedian: {median:.2f}\n25th: {p25:.2f}\n75th: {p75:.2f}'
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
    output_file_path: str = f"{data_dir}/plots/{test_name}_{container_name}_{configs}.png"

    print("Plotting LLC Load, Miss, and Instruction Frequencies over Time")
    print(f"Test Name: {test_name}")
    print(f"Container Name: {container_name}")
    print(f"Config: {configs}")
    print(f"Data Directory: {data_dir}")

    df: pd.DataFrame = load_data(data_dir)
    
    loads, loads_median, loads_25th, loads_75th = calculate_percentiles(df, "LOAD")
    misses, misses_median, misses_25th, misses_75th = calculate_percentiles(df, "MISS")
    instructions, instructions_median, instructions_25th, instructions_75th = calculate_percentiles(df, "INSTRUCTIONS")

    plt.style.use('ggplot')
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 12))

    plot_data(axes, loads, loads_median, loads_25th, loads_75th, "LLC Loads", "blue", "-", 0, "Loads")
    plot_data(axes, misses, misses_median, misses_25th, misses_75th, "LLC Misses", "red", "-", 0, "Misses")
    plot_data(axes, instructions, instructions_median, instructions_25th, instructions_75th, "Instructions", "green", "-", 1, "Instr")

    add_text_box(axes, 0, loads_median, loads_25th, loads_75th, "LLC Loads", "blue", 0)
    add_text_box(axes, 0, misses_median, misses_25th, misses_75th, "LLC Misses", "red", 0.25)
    add_text_box(axes, 1, instructions_median, instructions_25th, instructions_75th, "Instructions", "green", 0)

    fig.suptitle(f"TEST: {test_name} | SERVICE: {container_name} | CONFIGS: {configs}", fontsize=14, fontweight='bold', y=0.98)
    save_plot(fig, output_file_path)

if __name__ == "__main__":
    main()
