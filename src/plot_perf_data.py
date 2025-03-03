import matplotlib.pyplot as plt
import pandas as pd
import argparse
import numpy as np

parser = argparse.ArgumentParser(description="Plot LLC Load, Miss, and Instruction Frequencies over Time.")
parser.add_argument("--test-name", type=str, required=True, help="Test name")
parser.add_argument("--container-name", type=str, required=True, help="Service name")
parser.add_argument("--config", type=str, required=True, help="Configuration name")
parser.add_argument("--data-dir", type=str, required=True, help="Directory containing LLC data")

args = parser.parse_args()

test_name = args.test_name.replace(" ", "_")
container_name = args.container_name
configs = args.config.replace(" ", "_")
data_dir = args.data_dir

print("Plotting LLC Load, Miss, and Instruction Frequencies over Time")
print(f"Test Name: {test_name}")
print(f"Container Name: {container_name}")
print(f"Config: {configs}")
print(f"Data Directory: {data_dir}")\

output_file_path = data_dir + "/plots/" + test_name + "_" + container_name + "_" + configs + ".png"
llc_data_file = data_dir + "/data/llc_data.csv"

df = pd.read_csv(llc_data_file, sep=",")

df["Time"] = df["Time"] - df["Time"].min()

sample_print_limit = 20
print(f"Loaded {len(df)} samples from {llc_data_file}, printing first {sample_print_limit} samples:")
print(df.head(sample_print_limit))

loads = df[df["Type"] == "LOAD"]
misses = df[df["Type"] == "MISS"]
instructions = df[df["Type"] == "INSTRUCTIONS"]

num_loads = len(loads)
num_misses = len(misses)
num_instructions = len(instructions)

# TODO: have all plots have the same scale

fig, axes = plt.subplots(2, 1, figsize=(10, 10))

# Plot LLC Load and Misses on the first axes
axes[0].plot(loads["Time"], loads["Frequency"], label=f"LLC Loads (Samples: {num_loads})", color="blue", marker="o", linestyle="-")
axes[0].plot(misses["Time"], misses["Frequency"], label=f"LLC Misses (Samples: {num_misses})", color="red", marker="o", linestyle="-")

loads_median = np.median(loads["Frequency"])
misses_median = np.median(misses["Frequency"])

loads_25th = np.percentile(loads["Frequency"], 25)
misses_25th = np.percentile(misses["Frequency"], 25)

loads_75th = np.percentile(loads["Frequency"], 75)
misses_75th = np.percentile(misses["Frequency"], 75)

axes[0].axhline(loads_median, color="blue", linestyle="--", label="LLC Loads Median")
axes[0].axhline(misses_median, color="red", linestyle="--", label="LLC Misses Median")
axes[0].axhline(loads_25th, color="blue", linestyle=":", label="LLC Loads 25th Percentile")
axes[0].axhline(misses_25th, color="red", linestyle=":", label="LLC Misses 25th Percentile")
axes[0].axhline(loads_75th, color="blue", linestyle=":", label="LLC Loads 75th Percentile")
axes[0].axhline(misses_75th, color="red", linestyle=":", label="LLC Misses 75th Percentile")

axes[0].set_xlabel("Time (seconds)")
axes[0].set_ylabel("Frequency")
axes[0].set_title(f"TEST: {test_name}\nSERVICE: {container_name}        CONFIGS: {configs}")
axes[0].legend()
axes[0].grid()

# Plot Instructions on the second axes
axes[1].plot(instructions["Time"], instructions["Frequency"], label=f"Instructions (Samples: {num_instructions})", color="green", marker="o", linestyle="-")

instructions_median = np.median(instructions["Frequency"])
instructions_25th = np.percentile(instructions["Frequency"], 25)
instructions_75th = np.percentile(instructions["Frequency"], 75)

axes[1].axhline(instructions_median, color="green", linestyle="--", label="Instructions Median")
axes[1].axhline(instructions_25th, color="green", linestyle=":", label="Instructions 25th Percentile")
axes[1].axhline(instructions_75th, color="green", linestyle=":", label="Instructions 75th Percentile")

axes[1].set_xlabel("Time (seconds)")
axes[1].set_ylabel("Frequency")
axes[1].set_title("Instructions over Time")
axes[1].legend()
axes[1].grid()

# fig, ax1 = plt.subplots(figsize=(10, 6))

# # Plot LLC Load and Misses on the left y-axis
# ax1.plot(loads["Time"], loads["Frequency"], label=f"LLC Loads (Samples: {num_loads})", color="blue", marker="o", linestyle="-")
# ax1.plot(misses["Time"], misses["Frequency"], label=f"LLC Misses (Samples: {num_misses})", color="red", marker="o", linestyle="-")

# loads_median = np.median(loads["Frequency"])
# misses_median = np.median(misses["Frequency"])
# loads_25th = np.percentile(loads["Frequency"], 25)
# misses_25th = np.percentile(misses["Frequency"], 25)
# loads_75th = np.percentile(loads["Frequency"], 75)
# misses_75th = np.percentile(misses["Frequency"], 75)

# ax1.axhline(loads_median, color="blue", linestyle="--", label="LLC Loads Median")
# ax1.axhline(misses_median, color="red", linestyle="--", label="LLC Misses Median")
# ax1.axhline(loads_25th, color="blue", linestyle=":", label="LLC Loads 25th Percentile")
# ax1.axhline(misses_25th, color="red", linestyle=":", label="LLC Misses 25th Percentile")
# ax1.axhline(loads_75th, color="blue", linestyle=":", label="LLC Loads 75th Percentile")
# ax1.axhline(misses_75th, color="red", linestyle=":", label="LLC Misses 75th Percentile")

# ax1.set_xlabel("Time (seconds)")
# ax1.set_ylabel("Frequency (LLC Loads & Misses)")
# ax1.set_title(f"TEST: {test_name}\nSERVICE: {container_name}        CONFIGS: {configs}")
# ax1.grid()

# ax2 = ax1.twinx()

# # Plot Instructions on the right y-axis
# ax2.plot(instructions["Time"], instructions["Frequency"], label=f"Instructions (Samples: {num_instructions})", color="green", marker="o", linestyle="-")

# instructions_median = np.median(instructions["Frequency"])
# instructions_25th = np.percentile(instructions["Frequency"], 25)
# instructions_75th = np.percentile(instructions["Frequency"], 75)

# ax2.axhline(instructions_median, color="green", linestyle="--", label="Instructions Median")
# ax2.axhline(instructions_25th, color="green", linestyle=":", label="Instructions 25th Percentile")
# ax2.axhline(instructions_75th, color="green", linestyle=":", label="Instructions 75th Percentile")

# ax2.set_ylabel("Frequency (Instructions)")

# ax1.legend(loc="upper left")
# ax2.legend(loc="upper right")

plt.tight_layout()
plt.savefig(output_file_path)
print(f"Plot saved as {output_file_path}")