import matplotlib.pyplot as plt
import pandas as pd
import sys

if len(sys.argv) != 5:
    print("Usage: python3 plot_llc.py <test_name> <service_name> <config> <data_dir>")
    sys.exit(1)

test_name = sys.argv[1]
service_name = sys.argv[2]
configs = sys.argv[3]
data_dir = sys.argv[4]

configs = configs.replace(" ", "_")
output_file_path = data_dir + "/plots/" + test_name + "_" + service_name + "_" + configs + ".png"
llc_data_file = data_dir + "/data/llc_data.csv"

df = pd.read_csv(llc_data_file, sep=",", names=["Time", "Frequency", "Type"])
df["Time"] = df["Time"] - df["Time"].min()

loads = df[df["Type"] == "LOAD"]
misses = df[df["Type"] == "MISS"]
instructions = df[df["Type"] == "INSTRUCTIONS"]

num_loads = len(loads)
num_misses = len(misses)
num_instructions = len(instructions)

loads_5s = loads[loads["Time"] <= 5]
misses_5s = misses[misses["Time"] <= 5]
instructions_5s = instructions[instructions["Time"] <= 5]

num_loads_5s = len(loads_5s)
num_misses_5s = len(misses_5s)
num_instructions_5s = len(instructions_5s)

fig, axes = plt.subplots(2, 1, figsize=(10, 10))

axes[0].scatter(loads["Time"], loads["Frequency"], label=f"LLC Loads (Samples: {num_loads})", color="blue", marker="o")
axes[0].scatter(misses["Time"], misses["Frequency"], label=f"LLC Misses (Samples: {num_misses})", color="red", marker="o")
axes[0].scatter(instructions["Time"], instructions["Frequency"], label=f"Instructions (Samples: {num_instructions})", color="green", marker="o")
axes[0].set_xlabel("Time (seconds)")
axes[0].set_ylabel("Frequency")
axes[0].set_title(f"TEST: {test_name}\nSERVICE: {service_name}        CONFIGS: {configs}")
axes[0].legend()
axes[0].grid()

axes[1].scatter(loads_5s["Time"], loads_5s["Frequency"], label=f"LLC Loads (First 5s, Samples: {num_loads_5s})", color="blue", marker="o")
axes[1].scatter(misses_5s["Time"], misses_5s["Frequency"], label=f"LLC Misses (First 5s, Samples: {num_misses_5s})", color="red", marker="o")
axes[1].scatter(instructions_5s["Time"], instructions_5s["Frequency"], label=f"Instructions (First 5s, Samples: {num_instructions_5s})", color="green", marker="o")
axes[1].set_xlabel("Time (seconds)")
axes[1].set_ylabel("Frequency")
axes[1].set_title("Zoomed-in View: First 5 Seconds")
axes[1].legend()
axes[1].grid()

plt.tight_layout()
plt.savefig(output_file_path)
print(f"Plot saved as {output_file_path}")
