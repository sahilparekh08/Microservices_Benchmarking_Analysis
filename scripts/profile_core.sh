#!/bin/bash

CORE=""
CONFIG=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --core)
            CORE="$2"
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

if [[ -z "$CORE" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --core <core> --config <config> --data-dir <data_dir>"
    exit 1
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
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"
LOG_DIR="$DATA_DIR/logs"
PROFILE_DATA_OUTPUT_PATH="${DATA_DIR}/data/profile_data.csv"

DURATION=$((DURATION + 2))

echo "gcc -o $SRC_DIR/profile_core $SRC_DIR/profile_core.c"
gcc -o $SRC_DIR/profile_core $SRC_DIR/profile_core.c

echo -e "\nStarting profiler at $(date)"
echo "sudo $SRC_DIR/profile_core $CORE $DURATION $PROFILE_DATA_OUTPUT_PATH > $LOG_DIR/profile.log 2>&1"
sudo $SRC_DIR/profile_core $CORE $DURATION $PROFILE_DATA_OUTPUT_PATH > $LOG_DIR/profile.log 2>&1
echo "Finished at $(date)"

LEN_PROFILE_DATA=$(wc -l < "$PROFILE_DATA_OUTPUT_PATH")
LEN_PROFILE_DATA=$((LEN_PROFILE_DATA - 1))
if [[ $LEN_PROFILE_DATA -eq 0 ]]; then
    echo "No data collected, check $LOG_DIR/profile.log for details"
    exit 1
fi
echo "Collected $LEN_PROFILE_DATA lines of data"

echo -e "\nrm $SRC_DIR/profile_core"
rm $SRC_DIR/profile_core