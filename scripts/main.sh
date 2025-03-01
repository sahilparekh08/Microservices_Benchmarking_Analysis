#!/bin/bash

SERVICE_NAME=""
TEST_NAME=""
CONFIG=""
DATA_DIR=""
DOCKER_COMPOSE_DIR=""

make_dirs() {
    curr_time=$1
    
    echo "mkdir -p $DATA_DIR"
    mkdir -p $DATA_DIR

    echo "mkdir -p $DATA_DIR/$curr_time"
    mkdir -p $DATA_DIR/$curr_time

    echo "mkdir -p $DATA_DIR/$curr_time/data"
    mkdir -p $DATA_DIR/$curr_time/data

    echo "mkdir -p $DATA_DIR/$curr_time/plots"
    mkdir -p $DATA_DIR/$curr_time/plots
}



while [[ $# -gt 0 ]]; do
    case "$1" in
        --service_name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --test_name)
            TEST_NAME="$2"
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
        --docker_compose_dir)
            DOCKER_COMPOSE_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$SERVICE_NAME" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DATA_DIR" || -z "$DOCKER_COMPOSE_DIR" ]]; then
    echo "Usage: ./main.sh --service_name <service_name> --test_name <test_name> --config <config> --data_dir <data_dir> --docker_compose_dir <docker_compose_dir>"
    exit 1
fi

SRC_DIR="$(cd "$(dirname "$0")"/.. && pwd)/src"

curr_time=$(date)
echo "Started at time: $curr_time"

make_dirs $curr_time

echo "--------------------------------------------------"
echo "Running deathstar_clean_start.sh"
./scripts/deathstar_clean_start.sh "$DOCKER_COMPOSE_DIR"
echo "--------------------------------------------------"

echo "sleep 5"
sleep 5

echo "--------------------------------------------------"
echo "Running run_workload.sh"
./scripts/run_workload.sh --docker_compose_dir "$DOCKER_COMPOSE_DIR" --service_name "$SERVICE_NAME" --test_name "$TEST_NAME" --config "$CONFIG" > "$DATA_DIR/$curr_time/workload_output.log" &
echo "--------------------------------------------------"

echo "sleep 5"
sleep 5

echo "--------------------------------------------------"
echo "Running collect_llc_data_for_service.sh"
./scripts/collect_llc_data_for_service.sh "$SERVICE_NAME $TEST_NAME $CONFIG $DATA_DIR/$curr_time/ $SRC_DIR"
echo "--------------------------------------------------"

