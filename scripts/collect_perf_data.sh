#!/bin/bash

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 <SERVICE_NAME> <CONFIG> <DATA_DIR> [<SRC_DIR>]"
    exit 1
fi

SERVICE_NAME="$1"
DATA_DIR="$2"
CONFIG="$3"
SRC_DIR="${4:-"$(cd "$(dirname "$0")"/.. && pwd)/src"}"

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
