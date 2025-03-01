from traces_handler import get_trace_ids, get_services, parse_and_save_traces
import argparse
import os
from datetime import datetime

def process_traces(service_name: str, data_dir :str, limit: int) -> None:
    available_services = get_services()['data']
    if service_name not in available_services:
        print(f"Service '{service_name}' not found.")
        print(f"Available services: {', '.join(available_services)}")
        return
    
    trace_ids = get_trace_ids(service_name, limit)

    df = parse_and_save_traces(service_name, data_dir, trace_ids)
    df_csv_file_name = f"{service_name}_traces_data.csv"
    df_csv_file_path = os.path.join(data_dir, df_csv_file_name)
    df.to_csv(df_csv_file_path, index=False)
    print(f"Saved traces data to {df_csv_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse traces for a given service")
    parser.add_argument("service_name", type=str, help="Service name")
    parser.add_argument("data_dir", type=str, help="Data directory")
    parser.add_argument("limit", type=int, help="Limit of traces to analyse")
    args = parser.parse_args()
    print(f"Analysing [{args.limit}] traces for service [{args.service_name}] while saving them to [{args.data_dir}]")

    process_traces(args.service_name, args.data_dir, args.limit)
