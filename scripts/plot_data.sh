#!/bin/bash

# Parse command line arguments
TEST_NAME=""
CONTAINER_NAME=""
SERVICE_NAME_FOR_TRACES=""
CONFIG=""
DATA_DIR=""

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
        --service-name-for-traces)
            SERVICE_NAME_FOR_TRACES="$2"
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

# Check required arguments
if [[ -z "$TEST_NAME" || -z "$CONTAINER_NAME" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --test-name <test_name> --container-name <container_name> --service-name-for-traces <service_name> --config <config> --data-dir <data_dir>"
    exit 1
fi

echo "Plotting data with the following parameters:"
echo "  Test name: $TEST_NAME"
echo "  Container name: $CONTAINER_NAME"
echo "  Service name for traces: $SERVICE_NAME_FOR_TRACES"
echo "  Config: $CONFIG"
echo "  Data directory: $DATA_DIR"

# Get the directory of this script
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$(realpath "$SCRIPTS_DIR/../src")"

PLOT_BASE_DIR="$DATA_DIR/plots"
PROFILE_DATA_DIR="$DATA_DIR/data/profile_data"
TRACES_DATA_DIR="$DATA_DIR/data/traces"

# Run plot_profile_data.py
PLOT_DIR="$PLOT_BASE_DIR/perf"
mkdir -p "$PLOT_DIR"
CMD="python3 $SRC_DIR/profiling/visualization/plot_profile_data.py"
CMD="$CMD --test-name $TEST_NAME"
CMD="$CMD --container-name $CONTAINER_NAME"
CMD="$CMD --config $CONFIG"
CMD="$CMD --data-dir $PROFILE_DATA_DIR"
CMD="$CMD --plot-dir $PLOT_DIR"

echo "Running command: $CMD"
$CMD > "$DATA_DIR/logs/plot_profile_data.log" 2>&1 || {
    echo "Failed to plot profile data"
    exit 1
}

# Run plot_trace_data.py
PLOT_DIR="$PLOT_BASE_DIR/traces"
mkdir -p "$PLOT_DIR"
CMD="python3 $SRC_DIR/tracing/visualization/plot_trace_data.py"
CMD="$CMD --test-name $TEST_NAME"
CMD="$CMD --service-name-for-traces $SERVICE_NAME_FOR_TRACES"
CMD="$CMD --container-name $CONTAINER_NAME"
CMD="$CMD --config $CONFIG"
CMD="$CMD --data-dir $TRACES_DATA_DIR"
CMD="$CMD --plot-dir $PLOT_DIR"

echo "Running command: $CMD"
$CMD > "$DATA_DIR/logs/plot_trace_data.log" 2>&1 || {
    echo "Failed to plot trace data"
    exit 1
}

# Run plot_profile_with_traces.py
PLOT_DIR="$PLOT_BASE_DIR/perf_with_traces"
mkdir -p "$PLOT_DIR"
CMD="python3 $SRC_DIR/profile_with_traces/plot_profile_with_traces.py"
CMD="$CMD --test-name $TEST_NAME"
CMD="$CMD --service-name-for-traces $SERVICE_NAME_FOR_TRACES"
CMD="$CMD --container-name $CONTAINER_NAME"
CMD="$CMD --config $CONFIG"
CMD="$CMD --profile-data-dir $PROFILE_DATA_DIR"
CMD="$CMD --trace-data-dir $TRACES_DATA_DIR"
CMD="$CMD --plot-dir $PLOT_DIR"

echo "Running command: $CMD"
$CMD > "$DATA_DIR/logs/plot_profile_with_traces.log" 2>&1 || {
    echo "Failed to plot profile with traces data"
    exit 1
}

echo "Successfully plotted all data"
