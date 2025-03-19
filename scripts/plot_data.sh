#!/bin/bash

CONTAINER_NAME=""
SERVICE_NAME_FOR_TRACES=""
TEST_NAME=""
CONFIG=""
DATA_DIR=""
SRC_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --container-name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --service-name-for-traces)
            SERVICE_NAME_FOR_TRACES="$2"
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
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$CONTAINER_NAME" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: ./plot_data.sh --container-name <CONTAINER_NAME> --test-name <test_name> --config <config> --data-dir <data_dir>"
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$(realpath "$SCRIPTS_DIR/../src")"
PROFILE_SRC_DIR="${SRC_DIR}/profiling/visualization"
TRACE_SRC_DIR="${SRC_DIR}/tracing/visualization"
PROFILE_WITH_TRACES_DIR="${SRC_DIR}/profile_with_traces"

PLOT_BASE_DIR="$DATA_DIR/plots"

PLOT_DIR="$PLOT_BASE_DIR/perf"
PLOT_PROFILE_DATA_LOG_PATH="$DATA_DIR/logs/plot_profile_data.log"
echo -e "python3 $PROFILE_SRC_DIR/plot_profile_data.py  \\
    --test-name \"${TEST_NAME}\" \\
    --container-name \"${CONTAINER_NAME}\" \\ 
    --config \"${CONFIG}\" \\
    --data-dir \"${DATA_DIR}\" \\
    --plot-dir \"${PLOT_DIR}\" > $PLOT_PROFILE_DATA_LOG_PATH 2>&1"
python3 "$PROFILE_SRC_DIR/plot_profile_data.py" \
    --test-name "${TEST_NAME}" \
    --container-name "${CONTAINER_NAME}" \
    --config "${CONFIG}" \
    --data-dir "${DATA_DIR}" \
    --plot-dir "${PLOT_DIR}" > $PLOT_PROFILE_DATA_LOG_PATH 2>&1 || {
    echo "Error: Failed to plot performance data. See $PLOT_PROFILE_DATA_LOG_PATH for details."
    exit 1
}

PLOT_DIR="$PLOT_BASE_DIR/traces"
PLOT_JAEGER_DATA_LOG_PATH="$DATA_DIR/logs/plot_jaeger_data.log"
echo -e "\npython3 $TRACE_SRC_DIR/plot_jaeger_data.py \\
    --test-name \"${TEST_NAME}\" \\
    --service-name-for-traces \"${SERVICE_NAME_FOR_TRACES}\" \\
    --container-name \"${CONTAINER_NAME}\" \\
    --config \"${CONFIG}\" \\
    --data-dir \"${DATA_DIR}\" \\
    --plot-dir \"${PLOT_DIR}\" > $PLOT_JAEGER_DATA_LOG_PATH 2>&1"
python3 "$TRACE_SRC_DIR/plot_jaeger_data.py" \
    --test-name "${TEST_NAME}" \
    --service-name-for-traces "${SERVICE_NAME_FOR_TRACES}" \
    --container-name "${CONTAINER_NAME}" \
    --config "${CONFIG}" \
    --data-dir "${DATA_DIR}" \
    --plot-dir "${PLOT_DIR}" > $PLOT_JAEGER_DATA_LOG_PATH 2>&1 || {
    echo "Error: Failed to plot Jaeger data. See $PLOT_JAEGER_DATA_LOG_PATH for details."
    exit 1
}

PLOT_DIR="$PLOT_BASE_DIR/perf_with_traces"
PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH="$DATA_DIR/logs/plot_profile_with_trace_data.log"
echo -e "\npython3 $PROFILE_WITH_TRACES_DIR/visualization/plotting.py \\
    --test-name \"${TEST_NAME}\" \\
    --service-name-for-traces \"${SERVICE_NAME_FOR_TRACES}\" \\
    --container-name \"${CONTAINER_NAME}\" \\
    --config \"${CONFIG}\" \\
    --data-dir \"${DATA_DIR}\" \\
    --plot-dir \"${PLOT_DIR}\" > $PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH 2>&1"
python3 "$PROFILE_WITH_TRACES_DIR/visualization/plotting.py" \
    --test-name "${TEST_NAME}" \
    --service-name-for-traces "${SERVICE_NAME_FOR_TRACES}" \
    --container-name "${CONTAINER_NAME}" \
    --config "${CONFIG}" \
    --data-dir "${DATA_DIR}" \
    --plot-dir "${PLOT_DIR}" > "$PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH" 2>&1 || {
    echo "Error: Failed to plot performance data with traces. See $PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH for details."
    exit 1
}
