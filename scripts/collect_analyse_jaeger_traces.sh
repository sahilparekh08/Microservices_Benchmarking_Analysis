#!/bin/bash

SERVICE_NAME_FOR_TRACES=""
DATA_DIR=""
LIMIT=1
SRC_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
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
        --src-dir)
            SRC_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$SERVICE_NAME_FOR_TRACES" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --service-name <SERVICE_NAME_FOR_TRACES> --data-dir <data_dir> [--limit <limit>] [--src-dir <src_dir>]"
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"

PROCESS_JAEGER_TRACES_LOG_PATH="$DATA_DIR/logs/process_jaeger_traces.log"
DATA_DIR="$DATA_DIR/data"

echo "python3 $SRC_DIR/process_jaeger_traces.py $SERVICE_NAME_FOR_TRACES $DATA_DIR $LIMIT > $PROCESS_JAEGER_TRACES_LOG_PATH 2>&1"
python3 "$SRC_DIR/process_jaeger_traces.py" "$SERVICE_NAME_FOR_TRACES" "$DATA_DIR" "$LIMIT" > "$PROCESS_JAEGER_TRACES_LOG_PATH" 2>&1 || {
    echo "Error: Failed to process Jaeger traces. See $PROCESS_JAEGER_TRACES_LOG_PATH for details."
    exit 1
}
