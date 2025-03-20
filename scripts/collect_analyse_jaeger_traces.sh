#!/bin/bash

# Parse command line arguments
SERVICE_NAME=""
DATA_DIR=""
LIMIT=""
TEST_NAME=""
CONFIG=""
SAVE_TRACE_JSON=false
DEFAULT_SERVICE_NAME=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service-name-for-traces)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        --test-name)
            TEST_NAME="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --save-trace-json)
            SAVE_TRACE_JSON="$2"
            shift 2
            ;;
        --default-service-name)
            DEFAULT_SERVICE_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check required arguments
if [[ -z "$SERVICE_NAME" || -z "$DATA_DIR" || -z "$LIMIT" || -z "$TEST_NAME" || -z "$CONFIG" ]]; then
    echo "Usage: $0 --service-name-for-traces <service_name> --data-dir <data_dir> --limit <limit> --test-name <test_name> --config <config> [--save-trace-json <true/false>] [--default-service-name <default_service_name>]"
    exit 1
fi

DATA_DIR="$DATA_DIR/data/traces"

echo "Processing Jaeger traces with the following parameters:"
echo "  Service name: $SERVICE_NAME"
echo "  Data directory: $DATA_DIR"
echo "  Limit: $LIMIT"
echo "  Test name: $TEST_NAME"
echo "  Config: $CONFIG"
echo "  Save trace JSON: $SAVE_TRACE_JSON"
if [[ ! -z "$DEFAULT_SERVICE_NAME" ]]; then
    echo "  Default service name: $DEFAULT_SERVICE_NAME"
fi

# Get the directory of this script
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$(realpath "$SCRIPTS_DIR/../src")"

# Run the Python script
CMD="python3 $SRC_DIR/tracing/data_processing/process_jaeger_traces.py"
CMD="$CMD --service-name-for-traces $SERVICE_NAME"
CMD="$CMD --data-dir $DATA_DIR"
CMD="$CMD --limit $LIMIT"
CMD="$CMD --test-name $TEST_NAME"
CMD="$CMD --config $CONFIG"
CMD="$CMD --save-trace-json $SAVE_TRACE_JSON"

if [[ ! -z "$DEFAULT_SERVICE_NAME" ]]; then
    CMD="$CMD --default-service-name $DEFAULT_SERVICE_NAME"
fi

echo "Running command: $CMD"
$CMD > "$DATA_DIR/logs/process_jaeger_traces.log" 2>&1 || {
    echo "Failed to process Jaeger traces"
    exit 1
}

echo "Successfully processed Jaeger traces"