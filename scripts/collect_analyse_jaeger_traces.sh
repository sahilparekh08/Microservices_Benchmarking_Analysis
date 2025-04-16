#!/bin/bash

TEST_NAME=""
CONTAINER_NAME=""
CONFIG=""
SERVICE_NAME_FOR_TRACES=""
DATA_DIR=""
LIMIT=1
SAVE_TRACES_JSON=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test-name)
            TEST_NAME="$2"
            shift 2
            ;;
        --container-name)
            CONTAINER_NAME="$2"
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
        --non-idle-durations-dir)
            NON_IDLE_DURATIONS_DIR="$2"
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

if [[ -z "$TEST_NAME" || -z "$CONTAINER_NAME" || -z "$CONFIG" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$DATA_DIR" || -z "$NON_IDLE_DURATIONS_DIR" ]]; then
    echo "Usage: $0 --test-name TEST_NAME --config CONFIG --service-name-for-traces SERVICE_NAME_FOR_TRACES --data-dir DATA_DIR [--limit LIMIT] [--save-traces-json]"
    exit 1
fi

echo "Processing Jaeger traces with the following parameters:"
echo "  Test name: $TEST_NAME"
echo "  Container name: $CONTAINER_NAME"
echo "  Config: $CONFIG"
echo "  Service name for traces: $SERVICE_NAME_FOR_TRACES"
echo "  Data directory: $DATA_DIR"
echo "  Non-idle durations directory: $NON_IDLE_DURATIONS_DIR"
echo "  Limit: $LIMIT"
echo -e "  Save traces as JSON: $SAVE_TRACES_JSON\n"

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(realpath "$SCRIPTS_DIR/..")"
TRACE_SRC_DIR="$(realpath "$BASE_DIR/src/traces")"
PROCESS_JAEGER_TRACES_LOG_PATH="$DATA_DIR/logs/process_jaeger_traces.log"
COLLECT_NON_IDLE_DURATION_DATA_LOG_PATH="$DATA_DIR/logs/collect_non_idle_duration_data.log"
DATA_DIR="$DATA_DIR/data/trace_data"

if [ "$SAVE_TRACES_JSON" = true ]; then
    echo -e "Saving Jaeger traces as JSON in $DATA_DIR/data"

    echo -e "python3 \"$TRACE_SRC_DIR/process_jaeger_traces.py\" \\
        --service-name-for-traces \"$SERVICE_NAME_FOR_TRACES\" \\
        --data-dir \"$DATA_DIR\" \\
        --limit \"$LIMIT\" \\ 
        --test-name \"$TEST_NAME\" \\
        --config \"$CONFIG\" \\
        --save-traces-json > \"$PROCESS_JAEGER_TRACES_LOG_PATH\" 2>&1"

    python3 "$TRACE_SRC_DIR/process_jaeger_traces.py" \
        --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" \
        --data-dir "$DATA_DIR" \
        --limit "$LIMIT" \
        --test-name "$TEST_NAME" \
        --config "$CONFIG" \
        --save-traces-json > "$PROCESS_JAEGER_TRACES_LOG_PATH" 2>&1 || {
        echo "Error: Failed to process Jaeger traces. See $PROCESS_JAEGER_TRACES_LOG_PATH for details."
        exit 1
    }
else
    echo -e "python3 \"$TRACE_SRC_DIR/process_jaeger_traces.py\" \\
        --service-name-for-traces \"$SERVICE_NAME_FOR_TRACES\" \\
        --data-dir \"$DATA_DIR\" \\
        --limit \"$LIMIT\" \\
        --test-name \"$TEST_NAME\" \\
        --config \"$CONFIG\" > \"$PROCESS_JAEGER_TRACES_LOG_PATH\" 2>&1"

    python3 "$TRACE_SRC_DIR/process_jaeger_traces.py" \
        --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" \
        --data-dir "$DATA_DIR" \
        --limit "$LIMIT" \
        --test-name "$TEST_NAME" \
        --config "$CONFIG" > "$PROCESS_JAEGER_TRACES_LOG_PATH" 2>&1 || {
        echo "Error: Failed to process Jaeger traces. See $PROCESS_JAEGER_TRACES_LOG_PATH for details."
        exit 1
    }
fi

echo -e "\npython3 \"$TRACE_SRC_DIR/collect_non_idle_duration_data.py\" \\
    --test-name \"$TEST_NAME\" \\
    --service-name-for-traces \"$SERVICE_NAME_FOR_TRACES\" \\
    --container-name \"$CONTAINER_NAME\" \\
    --config \"$CONFIG\" \\
    --data-dir \"$DATA_DIR\" \\
    --non-idle-durations-dir \"$NON_IDLE_DURATIONS_DIR\" > \"$COLLECT_NON_IDLE_DURATION_DATA_LOG_PATH\" 2>&1"
python3 "$TRACE_SRC_DIR/collect_non_idle_duration_data.py" \
    --test-name "$TEST_NAME" \
    --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" \
    --container-name "$CONTAINER_NAME" \
    --config "$CONFIG" \
    --data-dir "$DATA_DIR" \
    --non-idle-durations-dir "$NON_IDLE_DURATIONS_DIR" > "$COLLECT_NON_IDLE_DURATION_DATA_LOG_PATH" 2>&1 || {
    echo "Error: Failed to collect non-idle median duration data. See $COLLECT_NON_IDLE_DURATION_DATA_LOG_PATH for details."
    exit 1
}
