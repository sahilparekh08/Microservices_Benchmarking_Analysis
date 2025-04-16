import argparse
import os
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect non-idle median duration data from traces")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name for traces")
    parser.add_argument("--container-name", type=str, required=True, help="Service name")
    parser.add_argument("--config", type=str, required=True, help="Test configuration")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--non-idle-durations-dir", type=str, help="Output directory for median durations")

    return parser.parse_args()

def load_traces_data(
    data_dir: str,
    service_name_for_traces: str,
    test_name: str,
    config: str,
    container_name: str
) -> pd.DataFrame:
    global DEFAULT_SERVICE_NAME

    jaeger_traces_csv_file_path: str = os.path.join(data_dir, f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv")
    if not os.path.exists(jaeger_traces_csv_file_path):
        print(f"File not found: {jaeger_traces_csv_file_path}, trying default service name: {DEFAULT_SERVICE_NAME}")
        jaeger_traces_csv_file_path: str = os.path.join(data_dir, f"{DEFAULT_SERVICE_NAME}_{test_name}_{config}_traces_data.csv")

    jaeger_traces_df: pd.DataFrame = pd.read_csv(jaeger_traces_csv_file_path)
    container_jaeger_traces_df: pd.DataFrame = jaeger_traces_df[jaeger_traces_df['container_name'] == container_name]
    return container_jaeger_traces_df

def get_trace_id_to_non_idle_intervals(traces_df: pd.DataFrame) -> Dict[str, List[Dict[int, int]]]:
    trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]] = {}
    for _, row in traces_df.iterrows():
        trace_id = row['trace_id']
        non_idle_intervals = row['non_idle_intervals'].split(";")
        for interval in non_idle_intervals:
            start, end = map(int, interval.split("-"))
            if trace_id not in trace_id_to_non_idle_intervals:
                trace_id_to_non_idle_intervals[trace_id] = []
            trace_id_to_non_idle_intervals[trace_id].append({start: end})
    if not trace_id_to_non_idle_intervals:
        print("No non idle intervals found in the trace data.")
        return {}
    
    for trace_id, intervals in trace_id_to_non_idle_intervals.items():
        sorted_intervals = sorted(intervals, key=lambda x: list(x.keys())[0])
        trace_id_to_non_idle_intervals[trace_id] = sorted_intervals

    # merge intervals for each trace id
    for trace_id, intervals in trace_id_to_non_idle_intervals.items():
        merged_intervals = []
        current_start, current_end = None, None
        for interval in intervals:
            for start, end in interval.items():
                if current_start is None:
                    current_start, current_end = start, end
                elif start <= current_end:
                    current_end = max(current_end, end)
                else:
                    merged_intervals.append({current_start: current_end})
                    current_start, current_end = start, end
        if current_start is not None:
            merged_intervals.append({current_start: current_end})
        trace_id_to_non_idle_intervals[trace_id] = merged_intervals

    return trace_id_to_non_idle_intervals

def get_median_non_idle_intervals(trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]]) -> int:
    # Calculate median number of non idle intervals across all traces
    non_idle_intervals_lens: List[int] = []
    for trace_id, non_idle_intervals in trace_id_to_non_idle_intervals.items():
        non_idle_intervals_lens.append(len(non_idle_intervals))
    if not non_idle_intervals_lens:
        print("No non idle intervals found for any traces.")
        return
    len_non_idle_intervals_to_count_map: Dict[int, int] = {}
    for length in non_idle_intervals_lens:
        if length not in len_non_idle_intervals_to_count_map:
            len_non_idle_intervals_to_count_map[length] = 0
        len_non_idle_intervals_to_count_map[length] += 1
    if len_non_idle_intervals_to_count_map:
        print(f"Non idle intervals length distribution: {len_non_idle_intervals_to_count_map}")
    non_idle_intervals_lens = sorted(non_idle_intervals_lens)
    median_non_idle_intervals: int = int(np.median(non_idle_intervals_lens))
    print(f"Median number of non idle intervals: {median_non_idle_intervals}")

    return median_non_idle_intervals

def get_median_duration_information_for_non_idle_intervals(
        trace_id_to_non_idle_intervals: Dict[str, List[Dict[int, int]]],
        median_non_idle_intervals: int
) -> Tuple[Dict[int, int], Dict[int, Dict[str, int]]]:
    # calculate the median duration for each non idle interval
    median_duration_per_non_idle_interval: Dict[int, int] = {}
    non_idle_duration_index_to_trace_id_non_idle_duration_map: Dict[int, Dict[str, int]] = {}
    for i in range(median_non_idle_intervals):
        non_idle_duration_index_to_trace_id_non_idle_duration_map[i] = {}
    for i in range(median_non_idle_intervals):
        durations: List[int] = []
        for trace_id, non_idle_intervals in trace_id_to_non_idle_intervals.items():
            non_idle_interval: Dict[int, int] = non_idle_intervals[i]
            start, end = list(non_idle_interval.items())[0]
            duration = end - start
            non_idle_duration_index_to_trace_id_non_idle_duration_map[i][trace_id] = duration
            durations.append(duration)
        median_duration_per_non_idle_interval[i] = int(np.median(durations))

    return median_duration_per_non_idle_interval, non_idle_duration_index_to_trace_id_non_idle_duration_map

def write_median_durations_to_csv(
        non_idle_durations_dir: str,
        container_name: str,
        test_name: str,
        config: str,
        median_duration_per_non_idle_interval: Dict[int, int],
) -> None:
    # write the median durations to a csv file
    if not non_idle_durations_dir:
        print("No median durations data directory provided.")
        return
    
    total_median_duration_across_non_idle_intervals: float = sum(median_duration_per_non_idle_interval.values())

    if non_idle_durations_dir:
        os.makedirs(non_idle_durations_dir, exist_ok=True)
        median_durations_test_dir = os.path.join(non_idle_durations_dir, test_name)
        os.makedirs(median_durations_test_dir, exist_ok=True)
        container_non_idle_durations_csv_file_name = os.path.join(median_durations_test_dir, f"{container_name}.csv")

        cache_partitions_str = ""
        config_parts = config.split("_")
        for part in config_parts:
            if part.startswith("cp"):
                cache_partitions_str = part[2:]
                break
        if not os.path.exists(container_non_idle_durations_csv_file_name):
            with open(container_non_idle_durations_csv_file_name, 'w') as f:
                f.write("cache_partitions,non_idle_duration\n")
        with open(container_non_idle_durations_csv_file_name, 'a') as f:
            f.write(f"{cache_partitions_str},{total_median_duration_across_non_idle_intervals}\n")
        print(f"Cache partitions: {cache_partitions_str}, Total median duration across non idle intervals: {total_median_duration_across_non_idle_intervals}")
        print(f"Median durations written to {container_non_idle_durations_csv_file_name}")

def main():
    args: argparse.Namespace = parse_arguments()
    test_name: str = args.test_name.replace(" ", "_")
    service_name_for_traces: str = args.service_name_for_traces
    container_name: str = args.container_name
    config: str = args.config.replace(" ", "_")
    data_dir: str = args.data_dir
    non_idle_durations_dir: str = args.non_idle_durations_dir

    print(f"Test Name: {test_name}")
    print(f"Service Name for Traces: {service_name_for_traces}")
    print(f"Container Name: {container_name}")
    print(f"Config: {config}")
    print(f"Data Directory: {data_dir}")
    print(f"Non Idle Durations Directory: {non_idle_durations_dir}")

    container_jaeger_traces_df: pd.DataFrame = load_traces_data(
        data_dir, service_name_for_traces, test_name, config, container_name)
    if container_jaeger_traces_df.empty:
        print(f"No traces found for container [{container_name}] with service name [{service_name_for_traces}]")
        return
    print("Container Jaeger Traces Data:")
    print(container_jaeger_traces_df.head())

    all_trace_ids_to_non_idle_intervals: Dict[str, List[Dict[int, int]]] = get_trace_id_to_non_idle_intervals(container_jaeger_traces_df)
    if not all_trace_ids_to_non_idle_intervals:
        print("No non-idle intervals found in traces.")
        return
    
    median_non_idle_intervals = get_median_non_idle_intervals(all_trace_ids_to_non_idle_intervals)
    # filter out traces with non idle intervals not equal to median
    filtered_trace_ids_to_non_idle_intervals = {trace_id: non_idle_intervals for trace_id, non_idle_intervals in all_trace_ids_to_non_idle_intervals.items() if len(non_idle_intervals) == median_non_idle_intervals}
    if not filtered_trace_ids_to_non_idle_intervals:
        print(f"No traces found with {median_non_idle_intervals} number of non idle intervals.")
        return
    
    median_duration_per_non_idle_interval, _ = get_median_duration_information_for_non_idle_intervals(filtered_trace_ids_to_non_idle_intervals, median_non_idle_intervals)

    write_median_durations_to_csv(non_idle_durations_dir, container_name, test_name, config, median_duration_per_non_idle_interval)

if __name__ == "__main__":
    main()
    