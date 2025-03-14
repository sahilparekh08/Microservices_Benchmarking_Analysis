#!/bin/bash

CONTAINER_NAME=""
CONFIG=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --container-name)
            CONTAINER_NAME="$2"
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

if [[ -z "$CONTAINER_NAME" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --container-name <container_name> --config <config> --data-dir <data_dir>"
    exit 1
fi

DURATION=0
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROFILE_SRC_DIR="$(realpath "$SCRIPTS_DIR/../src/profile")"
LOG_DIR="$DATA_DIR/logs"

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

DURATION=$((DURATION + 2))

echo -e "\nStarting at $(date)"

BOOT_TIME="$(cat /proc/stat | grep btime | awk '{print $2}')"

echo -e "\nStarting perf data collection at $(date)"
echo "sudo perf record -o "${CONTAINER_NAME}.data" \\
    -e LLC-loads -e LLC-load-misses -e instructions \\
    -F 40000 \\
    -p $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$CONTAINER_NAME" | awk '{print $1}')) \\
    -k CLOCK_MONOTONIC \\
    --timestamp \\
    -- sleep $DURATION || exit 1"
sudo perf record -o "${CONTAINER_NAME}.data" \
    -e LLC-loads -e LLC-load-misses -e instructions \
    -F 40000 \
    -p $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$CONTAINER_NAME" | awk '{print $1}')) \
    -k CLOCK_MONOTONIC \
    --timestamp \
    -- sleep $DURATION || exit 1
echo "Finished perf data collection at $(date)"

echo -e "\nsudo perf script -i \"${CONTAINER_NAME}.data\" > perf_output.txt || exit 1"
sudo perf script -i "${CONTAINER_NAME}.data" > perf_output.txt || exit 1

PERF_DATA_RAW_CSV_PATH="$DATA_DIR/data/perf_data_raw.csv"
PERF_DATA_UNPARSED_CSV_PATH="$DATA_DIR/data/perf_data_unparsed.csv"
PROFILE_DATA_CSV_PATH="$DATA_DIR/data/profile_data.csv"

echo -e "\nawk '/LLC-loads/ {gsub(\":\", \"\", \$3); print \$3 \",\" \$4 \",LOAD\"} 
     /LLC-load-misses/ {gsub(\":\", \"\", \$3); print \$3 \",\" \$4 \",MISS\"}
     /instructions/ {gsub(\":\", \"\", \$3); print \$3 "," \$4 ",INSTRUCTIONS"}' perf_output.txt >> \"$PERF_DATA_RAW_CSV_PATH\" || exit 1"
awk '/LLC-loads/ {gsub(":", "", $3); print $3 "," $4 ",LOAD"} 
     /LLC-load-misses/ {gsub(":", "", $3); print $3 "," $4 ",MISS"}
     /instructions/ {gsub(":", "", $3); print $3 "," $4 ",INSTRUCTIONS"}' perf_output.txt >> "$PERF_DATA_RAW_CSV_PATH" || exit 1

echo "echo \"Time,Frequency,Type\" > $PERF_DATA_UNPARSED_CSV_PATH"
echo "Time,Frequency,Type" > $PERF_DATA_UNPARSED_CSV_PATH

echo -e "\nawk -v boot_time=$BOOT_TIME 'BEGIN {FS=","; OFS=","} NR > 1 { \\
    split(\$1, time_parts, \".\"); \\
    timestamp_microsecs = (boot_time + time_parts[1]) * 1000000 + time_parts[2]; \\
    \$1 = timestamp_microsecs; \\
    print \$1, \$2, \$3 \\
}' \"$PERF_DATA_RAW_CSV_PATH\" >> \"$PERF_DATA_UNPARSED_CSV_PATH\""
awk -v boot_time=$BOOT_TIME 'BEGIN {FS=","; OFS=","} NR >= 1 { \
    split($1, time_parts, "."); \
    timestamp_microsecs = (boot_time + time_parts[1]) * 1000000 + time_parts[2]; \
    $1 = timestamp_microsecs; \
    print $1, $2, $3 \
}' "$PERF_DATA_RAW_CSV_PATH" >> "$PERF_DATA_UNPARSED_CSV_PATH"

echo -e "\npython3 $PROFILE_SRC_DIR/parse_perf_data.py \\
    --input-file \"$PERF_DATA_UNPARSED_CSV_PATH\" \\
    --output-file \"$PROFILE_DATA_CSV_PATH\" > $LOG_DIR/parse_perf_data.log 2>&1 || exit 1"
python3 $PROFILE_SRC_DIR/parse_perf_data.py \
    --input-file "$PERF_DATA_UNPARSED_CSV_PATH" \
    --output-file "$PROFILE_DATA_CSV_PATH" > $LOG_DIR/parse_perf_data.log 2>&1 || exit 1

echo -e "\nsudo rm -f \"${CONTAINER_NAME}.data\""
sudo rm -f "${CONTAINER_NAME}.data"

echo "sudo rm -f perf_output.txt"
sudo rm -f perf_output.txt

echo "sudo rm -f $PERF_DATA_RAW_CSV_PATH"
sudo rm -f $PERF_DATA_RAW_CSV_PATH

echo "sudo rm -f $PERF_DATA_UNPARSED_CSV_PATH"
sudo rm -f $PERF_DATA_UNPARSED_CSV_PATH

echo -e "\nFinished at $(date)"
