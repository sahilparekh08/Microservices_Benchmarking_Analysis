#!/bin/bash

CONTAINER_NAME=""
SERVICE_NAME_FOR_TRACES=""
TEST_NAME=""
CONFIG=""
DATA_DIR=""
SRC_DIR=""
SAVE_TRACE_PROFILE_CSVS=false
MEDIAN_DURATIONS_DATA_DIR=""

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
        --save-trace-profile-csvs)
            SAVE_TRACE_PROFILE_CSVS=true
            shift
            ;;
        --median-durations-data-dir)
            MEDIAN_DURATIONS_DATA_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$CONTAINER_NAME" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DATA_DIR" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$MEDIAN_DURATIONS_DATA_DIR" ]]; then
    echo "Usage: ./plot_data.sh --container-name <CONTAINER_NAME> --test-name <test_name> --config <config> --data-dir <data_dir> --service-name-for-traces <service_name_for_traces> --median-durations-data-dir <median_durations_data_dir> [--save-trace-profile-csvs]"
    exit 1
fi

echo "Plotting data with the following parameters:"
echo "CONTAINER_NAME: $CONTAINER_NAME"
echo "SERVICE_NAME_FOR_TRACES: $SERVICE_NAME_FOR_TRACES"
echo "TEST_NAME: $TEST_NAME"
echo "CONFIG: $CONFIG"
echo -e "DATA_DIR: $DATA_DIR\n"

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$(realpath "$SCRIPTS_DIR/../src")"
PROFILE_SRC_DIR="${SRC_DIR}/profile"
TRACE_SRC_DIR="${SRC_DIR}/trace"
PLOT_BASE_DIR="$DATA_DIR/plots"

if [[ "$SAVE_TRACE_PROFILE_CSVS" == true ]]; then
    mkdir -p "$DATA_DIR/data/trace_profile_csvs"
    TRACE_PROFILE_CSV_DIR="$DATA_DIR/data/trace_profile_csvs"
else
    TRACE_PROFILE_CSV_DIR=""
fi

PLOT_DIR="$PLOT_BASE_DIR/perf"
PLOT_PROFILE_DATA_LOG_PATH="$DATA_DIR/logs/plot_profile_data.log"
echo -e "python3 $PROFILE_SRC_DIR/plot_profile_data.py  \\
    --test-name \"${TEST_NAME}\" \\
    --container-name \"${CONTAINER_NAME}\" \\ 
    --config \"${CONFIG}\" \\
    --data-dir \"${DATA_DIR}/data/profile_data\" \\
    --plot-dir \"${PLOT_DIR}\" > $PLOT_PROFILE_DATA_LOG_PATH 2>&1"
python3 "$PROFILE_SRC_DIR/plot_profile_data.py" \
    --test-name "${TEST_NAME}" \
    --container-name "${CONTAINER_NAME}" \
    --config "${CONFIG}" \
    --data-dir "${DATA_DIR}/data/profile_data" \
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
    --data-dir \"${DATA_DIR}/data//trace_data\" \\
    --plot-dir \"${PLOT_DIR}\" > $PLOT_JAEGER_DATA_LOG_PATH 2>&1"
python3 "$TRACE_SRC_DIR/plot_jaeger_data.py" \
    --test-name "${TEST_NAME}" \
    --service-name-for-traces "${SERVICE_NAME_FOR_TRACES}" \
    --container-name "${CONTAINER_NAME}" \
    --config "${CONFIG}" \
    --data-dir "${DATA_DIR}/data/trace_data" \
    --plot-dir "${PLOT_DIR}" > $PLOT_JAEGER_DATA_LOG_PATH 2>&1 || {
    echo "Error: Failed to plot Jaeger data. See $PLOT_JAEGER_DATA_LOG_PATH for details."
    exit 1
}

PLOT_DIR="$PLOT_BASE_DIR/perf_with_traces"
PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH="$DATA_DIR/logs/plot_profile_with_trace_data.log"
echo -e "\npython3 $PROFILE_SRC_DIR/plot_profile_with_trace_data.py \\
    --test-name \"${TEST_NAME}\" \\
    --service-name-for-traces \"${SERVICE_NAME_FOR_TRACES}\" \\
    --container-name \"${CONTAINER_NAME}\" \\
    --config \"${CONFIG}\" \\
    --profile-data-dir \"${DATA_DIR}/data/profile_data\" \\
    --trace-data-dir \"${DATA_DIR}/data/trace_data\" \\
    --plot-dir \"${PLOT_DIR}\" \\
    --save-trace-profile-csvs ${SAVE_TRACE_PROFILE_CSVS} \\
    --trace-profile-csv-dir \"${TRACE_PROFILE_CSV_DIR}\" \\
    --median-durations-data-dir \"${MEDIAN_DURATIONS_DATA_DIR}\" > $PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH 2>&1"
python3 "$PROFILE_SRC_DIR/plot_profile_with_trace_data.py" \
    --test-name "${TEST_NAME}" \
    --service-name-for-traces "${SERVICE_NAME_FOR_TRACES}" \
    --container-name "${CONTAINER_NAME}" \
    --config "${CONFIG}" \
    --profile-data-dir "${DATA_DIR}/data/profile_data" \
    --trace-data-dir "${DATA_DIR}/data/trace_data" \
    --plot-dir "${PLOT_DIR}" \
    --save-trace-profile-csvs ${SAVE_TRACE_PROFILE_CSVS} \
    --trace-profile-csv-dir "${TRACE_PROFILE_CSV_DIR}" \
    --median-durations-data-dir "${MEDIAN_DURATIONS_DATA_DIR}" > $PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH 2>&1 || {
    echo "Error: Failed to plot performance data with traces. See $PLOT_PROFILE_WITH_TRACE_DATA_LOG_PATH for details."
    exit 1
}
