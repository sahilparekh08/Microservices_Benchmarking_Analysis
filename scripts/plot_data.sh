#!/bin/bash

SERVICE_NAME=""
TEST_NAME=""
CONFIG=""
DATA_DIR=""
SRC_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service_name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --test_name)
            TEST_NAME="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --data_dir)
            DATA_DIR="$2"
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

if [[ -z "$SERVICE_NAME" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DATA_DIR"]]; then
    echo "Usage: ./plot_data.sh --service_name <service_name> --test_name <test_name> --config <config> --data_dir <data_dir> [--src_dir <src_dir>]"
    exit 1
fi

SRC_DIR=${SRC_DIR:-"$(dirname "$0")/../src"}

echo "python3 $SRC_DIR/plot_llc_data.py \"${TEST_NAME}\" \"${SERVICE_NAME}\" \"${CONFIG}\" \"${DATA_DIR}\""
python3 $SRC_DIR/plot_llc_data.py "${TEST_NAME}" "${SERVICE_NAME}" "${CONFIG}" "${DATA_DIR}"

echo "python3 $SRC_DIR/plot_jaeger_data.py \"${TEST_NAME}\" \"${SERVICE_NAME}\" \"${CONFIG}\" \"${DATA_DIR}\""
python3 $SRC_DIR/plot_jaeger_data.py "${TEST_NAME}" "${SERVICE_NAME}" "${CONFIG}" "${DATA_DIR}"