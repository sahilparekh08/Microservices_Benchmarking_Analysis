from process_traces import get_trace_ids, get_services, parse_and_save_traces
import argparse
import os
from datetime import datetime

def analyse_traces(service_name: str, data_dir :str) -> None:
    available_services = get_services()['data']
    if service_name not in available_services:
        print(f"Service '{service_name}' not found.")
        print(f"Available services: {', '.join(available_services)}")
        return
    
    trace_ids = get_trace_ids(service_name)

    curr_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    data_dir_for_curr_run = os.path.join(data_dir, f"{curr_time}")
    os.makedirs(data_dir_for_curr_run, exist_ok=True)

    df = parse_and_save_traces(service_name, data_dir_for_curr_run, trace_ids)
    print(df.head())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse traces for a given service")
    parser.add_argument("service_name", type=str, help="Service name")
    parser.add_argument("data_dir", type=str, help="Data directory")
    args = parser.parse_args()
    print(f"Analysing traces for service [{args.service_name}] while saving them to [{args.data_dir}]")

    analyse_traces(args.service_name, args.data_dir)
