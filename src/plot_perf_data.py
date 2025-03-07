import matplotlib.pyplot as plt
import pandas as pd
import argparse
import numpy as np

def parse_arguments():
    parser = argparse.ArgumentParser(description="Plot LLC Load, Miss, and Instruction Frequencies over Time.")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Configuration name")
    parser.add_argument("--data-dir", type=str, required=True, help="Directory containing LLC data")
    
    return parser.parse_args()

def load_data(data_dir):
    llc_data_file = data_dir + "/data/llc_data.csv"
    df = pd.read_csv(llc_data_file, sep=",")
    df["Time"] = df["Time"] - df["Time"].min()
    return df

def calculate_percentiles(df, data_type):
    data = df[df["Type"] == data_type]
    median = np.median(data["Frequency"])
    p25 = np.percentile(data["Frequency"], 25)
    p75 = np.percentile(data["Frequency"], 75)
    return data, median, p25, p75

def plot_data(axes, data, median, p25, p75, label, color, linestyle, position, title):
    axes[position].plot(data["Time"], data["Frequency"], label=label, color=color, marker="o", linestyle=linestyle, markersize=4)
    axes[position].axhline(median, color=color, linestyle="--", label=f"{title} Median", alpha=0.7)
    axes[position].axhline(p25, color=color, linestyle=":", label=f"{title} 25th", alpha=0.5)
    axes[position].axhline(p75, color=color, linestyle=":", label=f"{title} 75th", alpha=0.5)

def add_text_box(axes, idx, median, p25, p75, label, color, y_offset=0):
    text = f'{label}\nMedian: {median:.2f}\n25th: {p25:.2f}\n75th: {p75:.2f}'
    bbox_props = dict(
        boxstyle="round,pad=0.5",
        facecolor="white",
        alpha=0.8,
        edgecolor=color,
        linewidth=2
    )
    axes[idx].annotate(
        text,
        xy=(1.02, 0.95 - y_offset),
        xycoords='axes fraction',
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='left',
        bbox=bbox_props
    )
    
def save_plot(fig, output_file_path):
    fig.tight_layout()
    plt.savefig(output_file_path, bbox_inches='tight', dpi=300)
    print(f"Plot saved as {output_file_path}")

def main():
    args = parse_arguments()

    test_name = args.test_name.replace(" ", "_")
    container_name = args.container_name
    configs = args.config.replace(" ", "_")
    data_dir = args.data_dir
    output_file_path = data_dir + "/plots/" + test_name + "_" + container_name + "_" + configs + ".png"

    print("Plotting LLC Load, Miss, and Instruction Frequencies over Time")
    print(f"Test Name: {test_name}")
    print(f"Container Name: {container_name}")
    print(f"Config: {configs}")
    print(f"Data Directory: {data_dir}")

    df = load_data(data_dir)
    
    loads, loads_median, loads_25th, loads_75th = calculate_percentiles(df, "LOAD")
    misses, misses_median, misses_25th, misses_75th = calculate_percentiles(df, "MISS")
    instructions, instructions_median, instructions_25th, instructions_75th = calculate_percentiles(df, "INSTRUCTIONS")

    plt.style.use('ggplot')
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 12))

    plot_data(axes, loads, loads_median, loads_25th, loads_75th, 
              f"LLC Loads ({len(loads)})", "blue", "-", 0, "Loads")
    plot_data(axes, misses, misses_median, misses_25th, misses_75th, 
              f"LLC Misses ({len(misses)})", "red", "-", 0, "Misses")
    
    plot_data(axes, instructions, instructions_median, instructions_25th, instructions_75th, 
              f"Instructions ({len(instructions)})", "green", "-", 1, "Instr")

    add_text_box(axes, 0, loads_median, loads_25th, loads_75th, "LLC Loads", "blue", 0)
    add_text_box(axes, 0, misses_median, misses_25th, misses_75th, "LLC Misses", "red", 0.25)
    add_text_box(axes, 1, instructions_median, instructions_25th, instructions_75th, "Instructions", "green", 0)

    fig.suptitle(f"TEST: {test_name} | SERVICE: {container_name} | CONFIGS: {configs}", 
                fontsize=14, fontweight='bold', y=0.98)
    
    axes[0].set_xlabel("Time (seconds)")
    axes[0].set_ylabel("Frequency")
    axes[0].set_title("LLC Loads and Misses over Time", fontsize=16, fontweight='bold', pad=50)
    axes[0].grid(True, linestyle='--', alpha=0.7)
    axes[0].set_ylim(bottom=0)
    
    handles, labels = axes[0].get_legend_handles_labels()
    order = [0, 2, 4, 1, 3, 5]
    handles = [handles[i] for i in order]
    labels = [labels[i] for i in order]
    axes[0].legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.15),
              ncol=3, frameon=True, fontsize=9)

    axes[1].set_xlabel("Time (seconds)")
    axes[1].set_ylabel("Frequency")
    axes[1].set_title("Instructions over Time", fontsize=16, fontweight='bold', pad=50)
    axes[1].grid(True, linestyle='--', alpha=0.7)
    axes[1].set_ylim(bottom=0)
    
    handles, labels = axes[1].get_legend_handles_labels()
    order = [0, 1, 2, 3]
    handles = [handles[i] for i in order]
    labels = [labels[i] for i in order]
    axes[1].legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.15),
              ncol=2, frameon=True, fontsize=9)

    plt.subplots_adjust(hspace=0.5, top=0.85)
    
    save_plot(fig, output_file_path)

if __name__ == "__main__":
    main()