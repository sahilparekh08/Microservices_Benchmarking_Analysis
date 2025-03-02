#!/bin/bash

SERVICE_NAME=""
CONFIG=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service-name)
            SERVICE_NAME="$2"
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

if [[ -z "$SERVICE_NAME" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --service-name <service_name> --config <config> --data-dir <data_dir>"
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

DURATION=$((DURATION + 5))

echo "sudo perf record -o "${SERVICE_NAME}.data" -e LLC-loads -e LLC-load-misses -e instructions -F 250 -p $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$SERVICE_NAME" | awk '{print $1}')) -g -- sleep $DURATION || exit 1"
sudo perf record -o "${SERVICE_NAME}.data" \
    -e LLC-loads -e LLC-load-misses -e instructions -F 250 \
    -p $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$SERVICE_NAME" | awk '{print $1}')) \
    -g -- sleep $DURATION || exit 1

echo "sudo perf script -i \"${SERVICE_NAME}.data\" > perf_output.txt || exit 1"
sudo perf script -i "${SERVICE_NAME}.data" > perf_output.txt || exit 1

LLC_DATA_CSV_PATH="$DATA_DIR/data/llc_data.csv"

echo "echo \"Time,Frequency,Type\" > $LLC_DATA_CSV_PATH"
echo "Time,Frequency,Type" > $LLC_DATA_CSV_PATH

echo "awk '/LLC-loads/ {gsub(\":\", \"\", \$3); print \$3 \",\" \$4 \",LOAD\"} 
     /LLC-load-misses/ {gsub(\":\", \"\", \$3); print \$3 \",\" \$4 \",MISS\"}
     /instructions/ {gsub(\":\", \"\", \$3); print \$3 "," \$4 ",INSTRUCTIONS"}' perf_output.txt >> \"$LLC_DATA_CSV_PATH\" || exit 1"
awk '/LLC-loads/ {gsub(":", "", $3); print $3 "," $4 ",LOAD"} 
     /LLC-load-misses/ {gsub(":", "", $3); print $3 "," $4 ",MISS"}
     /instructions/ {gsub(":", "", $3); print $3 "," $4 ",INSTRUCTIONS"}' perf_output.txt >> "$LLC_DATA_CSV_PATH" || exit 1

echo "sudo rm -f \"${SERVICE_NAME}.data\""
sudo rm -f "${SERVICE_NAME}.data"

echo "sudo rm -f perf_output.txt"
sudo rm -f perf_output.txt
