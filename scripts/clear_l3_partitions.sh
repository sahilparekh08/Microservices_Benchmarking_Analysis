#!/bin/bash

COS=""
LOG_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --cos)
            COS="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$COS" || -z "$LOG_DIR" ]]; then
    echo "Usage: $0 --cos <cos_value> --log-dir <log_dir_value>"
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(realpath "$SCRIPTS_DIR/..")"
PROFILE_SRC_DIR="$BASE_DIR/src/profile"
LOG_FILE_PATH="$LOG_DIR/clear_l3_partitions.log"

echo "COS: $COS"
echo "SCRIPTS_DIR: $SCRIPTS_DIR"
echo "BASE_DIR: $BASE_DIR"
echo "PROFILE_SRC_DIR: $PROFILE_SRC_DIR"
echo "LOG_FILE_PATH: $LOG_FILE_PATH"

cleanup() {
    CLEAR_L3_PARTITIONS_COMPILED_PATH="$PROFILE_SRC_DIR/clear_l3_partitions"
    if [[ -f "$CLEAR_L3_PARTITIONS_COMPILED_PATH" ]]; then
        echo -e "\nrm -f $CLEAR_L3_PARTITIONS_COMPILED_PATH"
        rm -f "$CLEAR_L3_PARTITIONS_COMPILED_PATH"
    fi
}

CMD="sudo gcc -o $PROFILE_SRC_DIR/clear_l3_partitions $PROFILE_SRC_DIR/clear_l3_partitions.c -lpqos -lm"
echo -e "\n$CMD"
$CMD || {
    echo "Failed to compile $PROFILE_SRC_DIR/clear_l3_partitions.c"
    exit 1
}

CMD="$PROFILE_SRC_DIR/clear_l3_partitions $COS"
echo -e "\n$CMD"
$CMD > "$LOG_FILE_PATH" 2>&1 || {
    echo "Failed to execute $PROFILE_SRC_DIR/clear_l3_partitions"
    exit 1
}

cleanup
