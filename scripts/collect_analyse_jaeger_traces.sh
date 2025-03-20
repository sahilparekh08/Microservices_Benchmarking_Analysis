#!/bin/bash

TEST_NAME=""
CONFIG=""
SERVICE_NAME_FOR_TRACES=""
DATA_DIR=""
LIMIT=1
SRC_DIR=""
SAVE_TRACES_JSON=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test-name)
            TEST_NAME="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --service-name-for-traces)
            SERVICE_NAME_FOR_TRACES="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --limit)
            LIMIT=$2
            if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [ "$LIMIT" -le 0 ]; then
                echo "Error: --limit must be a positive integer."
                exit 1
            fi
            shift 2
            ;;
        --save-traces-json)
            SAVE_TRACES_JSON=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$TEST_NAME" || -z "$CONFIG" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --test-name TEST_NAME --config CONFIG --service-name-for-traces SERVICE_NAME_FOR_TRACES --data-dir DATA_DIR [--limit LIMIT] [--save-traces-json]"
    exit 1
fi

echo "Processing Jaeger traces with the following parameters:"
echo "  Test name: $TEST_NAME"
echo "  Config: $CONFIG"
echo "  Service name for traces: $SERVICE_NAME_FOR_TRACES"
echo "  Data directory: $DATA_DIR"
echo "  Limit: $LIMIT"
echo "  Save traces as JSON: $SAVE_TRACES_JSON"

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TRACE_SRC_DIR="$(realpath "$SCRIPTS_DIR/../src/trace")"

PROCESS_JAEGER_TRACES_LOG_PATH="$DATA_DIR/logs/process_jaeger_traces.log"

CMD="python3 $TRACE_SRC_DIR/process_jaeger_traces.py"
CMD="$CMD --service-name-for-traces $SERVICE_NAME_FOR_TRACES"
CMD="$CMD --data-dir $DATA_DIR"
CMD="$CMD --limit $LIMIT"
CMD="$CMD --test-name $TEST_NAME"
CMD="$CMD --config $CONFIG"
if [ "$SAVE_TRACES_JSON" = true ]; then
    CMD="$CMD --save-traces-json"
fi

echo "Running command: $CMD > $PROCESS_JAEGER_TRACES_LOG_PATH 2>&1"
$CMD > $PROCESS_JAEGER_TRACES_LOG_PATH 2>&1 || {
    echo "Error: Failed to process Jaeger traces. See $PROCESS_JAEGER_TRACES_LOG_PATH for details."
    exit 1
}
