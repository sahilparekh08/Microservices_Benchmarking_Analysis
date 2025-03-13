from traces_handler import get_trace_ids, get_services, parse_and_save_traces
import argparse
import os

def parse_config_file(data_dir: str) -> dict:
    docker_container_service_config_path = os.path.join(data_dir, "docker_container_service_config.csv")
    if not os.path.exists(docker_container_service_config_path):
        print(f"[ERROR:] Docker container service config file [{docker_container_service_config_path}] not found.")
        SystemExit(1)

    jaeger_service_to_container_mapping = {}
    with open(docker_container_service_config_path, 'r') as f:
        # skip first line
        f.readline()
        for line in f:
            container_name, service_name = line.strip().split(",")
            jaeger_service_to_container_mapping[service_name] = container_name

    return jaeger_service_to_container_mapping

def process_traces(service_name_for_traces: str, data_dir :str, limit: int, test_name: str, config: str, jaeger_service_to_container_mapping: dict, save_traces_json: bool) -> None:
    available_services = get_services()['data']
    if service_name_for_traces not in available_services:
        print(f"[ERROR:] Service '{service_name_for_traces}' not found.")
        print(f"Available services: [{' , '.join(available_services)}]")
        SystemExit(1)
    
    trace_ids = get_trace_ids(service_name_for_traces, limit)

    curr_data_dir = os.path.join(data_dir, "data")
    df = parse_and_save_traces(service_name_for_traces, curr_data_dir, trace_ids, save_traces_json)
    if df is None:
        print(f"[ERROR:] No traces found for service '{service_name_for_traces}'")
        SystemExit(1)

    df['container_name'] = df['service'].apply(lambda x: jaeger_service_to_container_mapping[x] if x in jaeger_service_to_container_mapping else None)

    test_name = test_name.replace(" ", "_")
    config = config.replace(" ", "_")

    df_csv_file_name = f"{service_name_for_traces}_{test_name}_{config}_traces_data.csv"
    df_csv_file_path = os.path.join(curr_data_dir, df_csv_file_name)
    df.to_csv(df_csv_file_path, index=False)

    print(f"Saved traces data to {df_csv_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse traces for a given service")
    parser.add_argument("--service-name-for-traces", type=str, required=True, help="Service name")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--limit", type=int, required=True, help="Limit of traces to analyse")
    parser.add_argument("--test-name", type=str, required=True, help="Test name")
    parser.add_argument("--config", type=str, required=True, help="Test config")
    parser.add_argument("--save-trace-json", type=bool, default=False, help="Save trace jsons")

    args = parser.parse_args()
    print(f"Processing jaeger traces for following args:\n\tservice_name_for_traces [{args.service_name_for_traces}]\n\tdata_dir [{args.data_dir}]\n\tlimit [{args.limit}]\n\ttest_name [{args.test_name}]\n\tconfig [{args.config}]\n\tsave_trace_json [{args.save_trace_json}]")

    jaeger_service_to_container_mapping = parse_config_file(args.data_dir)

    process_traces(args.service_name_for_traces, args.data_dir, args.limit, args.test_name, args.config, jaeger_service_to_container_mapping, args.save_trace_json)
