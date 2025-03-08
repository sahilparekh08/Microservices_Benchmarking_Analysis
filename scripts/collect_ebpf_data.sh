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

echo -e "\nStarting at $(date)"

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"

echo -e "\npython3 $SRC_DIR/collect_ebpf_data.py \\
    --pid $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$CONTAINER_NAME" | awk '{print $1}')) \\
    --duration $DURATION \\
    --output \"$DATA_DIR/data/ebpf_data.csv\""
sudo python3 "$SRC_DIR/collect_ebpf_data.py" \
    --pid $(docker inspect --format '{{.State.Pid}}' $(docker ps -a | grep "$CONTAINER_NAME" | awk '{print $1}')) \
    --duration $DURATION \
    --output "$DATA_DIR/data/ebpf_data.csv"

echo -e "\nFinished at $(date)"