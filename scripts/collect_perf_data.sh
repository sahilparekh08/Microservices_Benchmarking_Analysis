#!/bin/bash

SERVICE_NAME=""
CONFIG=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --service_name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --data_dir)
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
    echo "Usage: $0 --service_name <service_name> --config <config> --data_dir <data_dir>"
    exit 1
fi

DURATION=0

IFS=' ' read -r -a CONFIG <<< "$CONFIG"
for i in "${CONFIG[@]}"; do
    case "$i" in
        d*)
            DURATION="${i:1}"
            ;;
        *)
            echo "Unknown option: $i"
            exit 1
    esac
done

DURATION=$((DURATION + 5))

echo "sudo perf record -o "${SERVICE_NAME}.data" -e LLC-loads -e LLC-load-misses -e instructions -F 250 -p $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$SERVICE_NAME" | awk '{print $1}')) -g -- sleep $DURATION"
sudo perf record -o "${SERVICE_NAME}.data" \
    -e LLC-loads -e LLC-load-misses -e instructions -F 250 \
    -p $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$SERVICE_NAME" | awk '{print $1}')) \
    -g -- sleep $DURATION

echo "sudo perf script -i \"${SERVICE_NAME}.data\" > perf_output.txt"
sudo perf script -i "${SERVICE_NAME}.data" > perf_output.txt

echo "awk '/LLC-loads/ {gsub(\":\", \"\", \$3); print \$3 \",\" \$4 \",LOAD\"} 
     /LLC-load-misses/ {gsub(\":\", \"\", \$3); print \$3 \",\" \$4 \",MISS\"}
     /instructions/ {gsub(\":\", \"\", \$3); print \$3 "," \$4 ",INSTRUCTIONS"}' perf_output.txt > $DATA_DIR/data/llc_data.csv"
awk '/LLC-loads/ {gsub(":", "", $3); print $3 "," $4 ",LOAD"} 
     /LLC-load-misses/ {gsub(":", "", $3); print $3 "," $4 ",MISS"}
     /instructions/ {gsub(":", "", $3); print $3 "," $4 ",INSTRUCTIONS"}' perf_output.txt > "$DATA_DIR/data/llc_data.csv"

echo "sudo rm -f \"${SERVICE_NAME}.data\""
sudo rm -f "${SERVICE_NAME}.data"

echo "sudo rm -f perf_output.txt"
sudo rm -f perf_output.txt
