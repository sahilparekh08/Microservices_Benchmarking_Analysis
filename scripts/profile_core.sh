#!/bin/bash

CORE_TO_PIN=""
TARGET_CORES=""
DURATION=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --core-to-pin)
            CORE_TO_PIN="$2"
            shift 2
            ;;
        --target-cores)
            TARGET_CORES="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
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

if [[ -z "$CORE_TO_PIN" || -z "$TARGET_CORES" || -z "$DURATION" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --core-to-pin <core_to_pin> --target-core <TARGET_CORES> --duration <duration in seconds> --data-dir <data_dir>"
    exit 1
fi

echo "Profiling with the following parameters:"
echo "  Core to pin: $CORE_TO_PIN"
echo "  Target cores: $TARGET_CORES"
echo "  Duration: $DURATION"
echo "  Data directory: $DATA_DIR"

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$(realpath "$SCRIPTS_DIR/../src")"
PROFILE_SRC_DIR="$SRC_DIR/profile"
LOG_DIR="$DATA_DIR/logs"
PROFILE_DATA_DIR="$DATA_DIR/data/profile_data"

cleanup() {
    PROFILE_CORE_COMPILED_PATH="$PROFILE_SRC_DIR/profile_core"
    DECODE_PROFILED_DATA_COMPILED_PATH="$PROFILE_SRC_DIR/decode_profiled_data"

    if [[ -f "$PROFILE_CORE_COMPILED_PATH" ]]; then
        echo -e "\nrm $PROFILE_CORE_COMPILED_PATH"
        rm "$PROFILE_CORE_COMPILED_PATH"
    fi

    if [[ -f "$DECODE_PROFILED_DATA_COMPILED_PATH" ]]; then
        echo "rm $DECODE_PROFILED_DATA_COMPILED_PATH"
        rm "$DECODE_PROFILED_DATA_COMPILED_PATH"
    fi
}

CMD="sudo gcc -O0 -g -Wall $PROFILE_SRC_DIR/profile_core.c -o $PROFILE_SRC_DIR/profile_core -lrt"
echo -e "\n$CMD"
$CMD || {
    echo "Failed to compile profile_core.c"
    exit 1
}

CMD="sudo gcc -O3 -Wall $PROFILE_SRC_DIR/decode_profiled_data.c -o $PROFILE_SRC_DIR/decode_profiled_data"
echo -e "\n$CMD"
$CMD || {
    echo "Failed to compile decode_profiled_data.c"
    exit 1
}

CMD="sudo $PROFILE_SRC_DIR/profile_core --core-to-pin $CORE_TO_PIN --target-cores $TARGET_CORES --duration $DURATION --data-dir $PROFILE_DATA_DIR"
echo -e "\nStarting profiler at $(date)"
echo "$CMD > $LOG_DIR/profile_core.log 2>&1"
$CMD > $LOG_DIR/profile_core.log 2>&1 || {
    echo "Failed to run profile_core"
    cleanup
    exit 1
}
echo -e "Finished at $(date)"

CMD="sudo $PROFILE_SRC_DIR/decode_profiled_data --data-dir $PROFILE_DATA_DIR"
echo -e "\n$CMD > $LOG_DIR/decode_profiled_data.log 2>&1"
$CMD > $LOG_DIR/decode_profiled_data.log 2>&1 || {
    echo "Failed to run decode_profiled_data"
    cleanup
    exit 1
}

cleanup
