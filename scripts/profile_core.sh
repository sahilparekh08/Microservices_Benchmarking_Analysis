#!/bin/bash

CORE_TO_PIN=""
TARGET_CORES=""
CONFIG=""
DATA_DIR=""
MAX_SAMPLES=""

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
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --max-samples)
            MAX_SAMPLES="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$CORE_TO_PIN" || -z "$TARGET_CORES" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --core-to-pin <core_to_pin> --target-cores <TARGET_CORES> --config <config> --data-dir <data_dir> [--max-samples <max_samples>]"
    exit 1
fi

echo "Profiling with the following parameters:"
echo "  Core to pin: $CORE_TO_PIN"
echo "  Target cores: $TARGET_CORES"
echo "  Config: $CONFIG"
echo "  Data directory: $DATA_DIR"
if [[ ! -z "$MAX_SAMPLES" ]]; then
    echo "  Max samples: $MAX_SAMPLES"
fi

DURATION=0

IFS=' ' read -r -a CONFIG <<< "$CONFIG"
for i in "${CONFIG[@]}"; do
    case "$i" in
        d*)
            DURATION="${i:1}"
            ;;
    esac
done

if [[ $DURATION -eq 0 ]]; then
    echo "Duration not provided in config"
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$(realpath "$SCRIPTS_DIR/../src")"
PROFILE_SRC_DIR="$SRC_DIR/profiling/core"
LOG_DIR="$DATA_DIR/logs"
PROFILE_DATA_DIR="$DATA_DIR/data/profile_data"

DURATION=$((DURATION + 5))

cleanup() {
    PROFILE_CORE_COMPILED_PATH="$PROFILE_SRC_DIR/src/profile_core"
    DECODE_PROFILED_DATA_COMPILED_PATH="$PROFILE_SRC_DIR/src/decode_profiled_data"

    if [[ -f "$PROFILE_CORE_COMPILED_PATH" ]]; then
        echo "rm $PROFILE_CORE_COMPILED_PATH"
        rm "$PROFILE_CORE_COMPILED_PATH"
    fi

    if [[ -f "$DECODE_PROFILED_DATA_COMPILED_PATH" ]]; then
        echo "rm $DECODE_PROFILED_DATA_COMPILED_PATH"
        rm "$DECODE_PROFILED_DATA_COMPILED_PATH"
    fi
}

echo -e "\nsudo gcc -O0 -g -Wall $PROFILE_SRC_DIR/src/profile_core.c -o $PROFILE_SRC_DIR/src/profile_core -lrt"
sudo gcc -O0 -g -Wall $PROFILE_SRC_DIR/src/profile_core.c -o $PROFILE_SRC_DIR/src/profile_core -lrt || {
    echo "Failed to compile profile_core.c"
    exit 1
}

echo "sudo gcc -O3 -Wall $PROFILE_SRC_DIR/src/decode_profiled_data.c -o $PROFILE_SRC_DIR/src/decode_profiled_data"
sudo gcc -O3 -Wall $PROFILE_SRC_DIR/src/decode_profiled_data.c -o $PROFILE_SRC_DIR/src/decode_profiled_data || {
    echo "Failed to compile decode_profiled_data.c"
    exit 1
}

echo -e "\nStarting profiler at $(date)"
CMD="sudo $PROFILE_SRC_DIR/src/profile_core --core-to-pin $CORE_TO_PIN --target-cores $TARGET_CORES --duration $DURATION --output-dir $PROFILE_DATA_DIR"
if [[ ! -z "$MAX_SAMPLES" ]]; then
    CMD="$CMD --max-samples $MAX_SAMPLES"
fi
echo "$CMD > $LOG_DIR/profile_core.log 2>&1"
$CMD > $LOG_DIR/profile_core.log 2>&1 || {
    echo "Failed to run profile_core"
    cleanup
    exit 1
}
echo -e "Finished at $(date)\n"

echo "sudo $PROFILE_SRC_DIR/src/decode_profiled_data --input-dir $PROFILE_DATA_DIR --output-dir $PROFILE_DATA_DIR > $LOG_DIR/decode_profiled_data.log 2>&1"
sudo $PROFILE_SRC_DIR/src/decode_profiled_data --input-dir $PROFILE_DATA_DIR --output-dir $PROFILE_DATA_DIR > $LOG_DIR/decode_profiled_data.log 2>&1 || {
    echo "Failed to run decode_profiled_data"
    cleanup
    exit 1
}

echo -e "\nrm $PROFILE_SRC_DIR/src/profile_core $PROFILE_SRC_DIR/src/decode_profiled_data"
rm $PROFILE_SRC_DIR/src/profile_core $PROFILE_SRC_DIR/src/decode_profiled_data

if [[ $(find "$PROFILE_DATA_DIR" -type f -name "*.bin" | wc -l) -gt 0 ]]; then
    echo "Removing existing .bin files in $PROFILE_DATA_DIR"
    rm "$PROFILE_DATA_DIR"/*.bin
fi

cleanup
