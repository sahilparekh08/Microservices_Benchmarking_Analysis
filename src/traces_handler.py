import requests
import pandas as pd
from typing import Any, Dict, List
from span_data import SpanData

JAEGER_URL = "http://localhost:16686"
JAEGER_SERVICES_API_PATH = "/api/services"
JAEGER_TRACES_API_PATH = "/api/traces"

def get_trace_ids(service_name: str, limit: int) -> Dict[str, Any]:
    url = f"{JAEGER_URL}{JAEGER_TRACES_API_PATH}"
    params = {"service": service_name, "limit": limit}
    
    try:
        print(f"Fetching traces from [{url}] with params [{params}]")
        response = requests.get(url, params=params)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise err
    
    traces = response.json().get("data", [])
    trace_ids = [trace.get("traceID", "unknown") for trace in traces]
    print(f"Trace IDs fetched successfully")
    return trace_ids

def get_services() -> List[str]:
    url = f"{JAEGER_URL}{JAEGER_SERVICES_API_PATH}"
    
    try:
        print(f"Fetching services from {url}")
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise err
    
    services = response.json()
    print("Services fetched successfully")
    return services


def parse_and_save_traces(service_name: str, data_dir_for_curr_run: str, trace_ids: List[Any]) -> pd.DataFrame:
    records = []
    num_traces = len(trace_ids)
    counter = 0

    for trace_id in trace_ids:
        counter += 1

        url = f"{JAEGER_URL}{JAEGER_TRACES_API_PATH}/{trace_id}"

        try:
            print(f"Fetching trace from [{url}]")
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            raise err
        
        trace = response.json().get("data", None)
        if not trace:
            print(f"Skipping trace [{trace_id}] due to missing data")
            continue

        if len(trace) != 1:
            print(f"Skipping trace [{trace_id}] due to invalid data, expected 1 trace, got {len(trace)}")
            continue

        trace = trace[0]

        trace_id = trace.get("traceID", "unknown")
        save_trace_to_file(service_name, data_dir_for_curr_run, trace_id, response.text)

        print(f"[{counter}/{num_traces}] Parsing trace [{trace_id}]")

        span_id_to_span_map = create_span_data_graph(trace)

        for span_id, span in span_id_to_span_map.items():
            records.append({
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "service": span.service,
                "operation": span.operation,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "duration": span.duration,
                "non_idle_execution_time": span.non_idle_execution_time,
            })

    return pd.DataFrame(records)

def create_span_data_graph(trace: Dict[str, Any]) -> Dict[str, SpanData]:
    trace_id = trace.get("traceID", "unknown")
    
    span_id_to_span = {}

    for span in trace.get("spans", []):
        span_id = span.get("spanID", "unknown")
        trace_id = span.get("traceID", "unknown")
        service = span.get("operationName", "unknown")
        operation = span.get("operationName", "unknown")
        start_time = span.get("startTime", 0)
        duration = span.get("duration", 0)
        span_data = SpanData(trace_id=trace_id, span_id=span_id, service=service, operation=operation,
                             start_time=start_time, duration=duration)
        span_id_to_span[span_id] = span_data

    for span in trace.get("spans", []):
        span_id = span.get("spanID", "unknown")
        references = span.get("references", [])

        for reference in references:
            ref_type = reference.get("refType", "")
            parent_span_id = reference.get("spanID", "unknown")
            if ref_type == "CHILD_OF" and parent_span_id in span_id_to_span:
                parent_span = span_id_to_span[parent_span_id]
                child_span = span_id_to_span[span_id]
                parent_span.add_child(child_span)

    return span_id_to_span

def save_trace_to_file(service_name: str, data_dir_for_curr_run: str, trace_id: str, trace_text: str) -> None:
    file_path = f"{data_dir_for_curr_run}/{service_name}_{trace_id}.json"

    with open(file_path, "w") as file:
        file.write(trace_text)