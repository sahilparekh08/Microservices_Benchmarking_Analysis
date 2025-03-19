#!/bin/bash

CORE_TO_PIN=""
TARGET_CORE=""
CONFIG=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --core-to-pin)
            CORE_TO_PIN="$2"
            shift 2
            ;;
        --target-core)
            TARGET_CORE="$2"
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

if [[ -z "$CORE_TO_PIN" || -z "$TARGET_CORE" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --core-to-pin <core_to_pin> --target-core <target_core> --config <config> --data-dir <data_dir>"
    exit 1
fi

echo "Profiling with the following parameters:"
echo "  Core to pin: $CORE_TO_PIN"
echo "  Target core: $TARGET_CORE"
echo "  Config: $CONFIG"
echo "  Data directory: $DATA_DIR"

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
PROFILE_DATA_OUTPUT_PATH="${DATA_DIR}/data/profile_data.csv"
PROFILE_DATA_BIN_PATH="$DATA_DIR/data/profile_data.bin"

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
echo "sudo $PROFILE_SRC_DIR/src/profile_core $CORE_TO_PIN $TARGET_CORE $DURATION $PROFILE_DATA_BIN_PATH > $LOG_DIR/profile_core.log 2>&1"
sudo $PROFILE_SRC_DIR/src/profile_core $CORE_TO_PIN $TARGET_CORE $DURATION $PROFILE_DATA_BIN_PATH > $LOG_DIR/profile_core.log 2>&1 || {
    echo "Failed to run profile_core"
    cleanup
    exit 1
}
echo -e "Finished at $(date)\n"

echo "sudo $PROFILE_SRC_DIR/src/decode_profiled_data $PROFILE_DATA_BIN_PATH $PROFILE_DATA_OUTPUT_PATH > $LOG_DIR/decode_profiled_data.log 2>&1"
sudo $PROFILE_SRC_DIR/src/decode_profiled_data $PROFILE_DATA_BIN_PATH $PROFILE_DATA_OUTPUT_PATH > $LOG_DIR/decode_profiled_data.log 2>&1 || {
    echo "Failed to run decode_profiled_data"
    cleanup
    exit 1
}

LEN_PROFILED_DATA=$(wc -l < "$PROFILE_DATA_OUTPUT_PATH")
LEN_PROFILED_DATA=$((LEN_PROFILED_DATA - 1))
echo -e "\n$LEN_PROFILED_DATA lines of profiled data written to $PROFILE_DATA_OUTPUT_PATH"

echo -e "\nrm $PROFILE_SRC_DIR/src/profile_core $PROFILE_SRC_DIR/src/decode_profiled_data"
rm $PROFILE_SRC_DIR/src/profile_core $PROFILE_SRC_DIR/src/decode_profiled_data

echo "rm $PROFILE_DATA_BIN_PATH"
rm $PROFILE_DATA_BIN_PATH

cleanup
