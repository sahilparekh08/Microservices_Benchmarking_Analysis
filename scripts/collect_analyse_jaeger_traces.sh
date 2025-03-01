#!/bin/bash

SERVICE_NAME=""
DATA_DIR=""
LIMIT=1
SRC_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service_name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --data_dir)
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
        --src_dir)
            SRC_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$SERVICE_NAME" || -z "$DATA_DIR"]]; then
    echo "Usage: $0 --service_name <service_name> --data_dir <data_dir> [--limit <limit>] [--src_dir <src_dir>]"
    exit 1
fi

SRC_DIR=${SRC_DIR:-"$(dirname "$0")/../src"}

python3 "$SRC_DIR/analyse_jaeger_traces.py" "$SERVICE_NAME" "$DATA_DIR" "$LIMIT"
