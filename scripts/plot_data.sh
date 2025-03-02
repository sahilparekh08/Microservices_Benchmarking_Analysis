#!/bin/bash

SERVICE_NAME=""
TEST_NAME=""
CONFIG=""
DATA_DIR=""
SRC_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service-name)
            SERVICE_NAME="$2"
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
        --data-dir)
            DATA_DIR="$2"
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

if [[ -z "$SERVICE_NAME" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: ./plot_data.sh --service-name <service_name> --test-name <test_name> --config <config> --data-dir <data_dir> [--src-dir <src_dir>]"
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"

PLOT_PERF_DATA_LOG_PATH="$DATA_DIR/logs/plot_perf_data.log"
echo "python3 $SRC_DIR/plot_perf_data.py \"${TEST_NAME}\" \"${SERVICE_NAME}\" \"${CONFIG}\" \"${DATA_DIR}\" > $PLOT_PERF_DATA_LOG_PATH 2>&1"
python3 $SRC_DIR/plot_perf_data.py "${TEST_NAME}" "${SERVICE_NAME}" "${CONFIG}" "${DATA_DIR}" > "$PLOT_PERF_DATA_LOG_PATH" 2>&1 || {
    echo "Error: Failed to plot performance data. See $PLOT_PERF_DATA_LOG_PATH for details."
    exit 1
}

PLOT_JAEGER_DATA_LOG_PATH="$DATA_DIR/logs/plot_jaeger_data.log"
echo -e "\npython3 $SRC_DIR/plot_jaeger_data.py \"${TEST_NAME}\" \"${SERVICE_NAME}\" \"${CONFIG}\" \"${DATA_DIR}\" > $PLOT_JAEGER_DATA_LOG_PATH 2>&1"
python3 $SRC_DIR/plot_jaeger_data.py "${TEST_NAME}" "${SERVICE_NAME}" "${CONFIG}" "${DATA_DIR}" > "$PLOT_JAEGER_DATA_LOG_PATH" 2>&1 || {
    echo "Error: Failed to plot Jaeger data. See $PLOT_JAEGER_DATA_LOG_PATH for details."
    exit 1
}