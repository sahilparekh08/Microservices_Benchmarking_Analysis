#!/bin/bash

SERVICE_NAME=""
SERVICE_NAME_FOR_TRACES=""
TEST_NAME=""
CONFIG=""
DOCKER_COMPOSE_DIR=""

usage() {    
    echo "Usage: ./main.sh --service-name <service-name> --service-name-for-traces <service-name-for-traces> --test-name <test-name> --config <config> --docker-compose-dir <docker-compose-dir>"
    echo "Arg examples:"
    echo "  --service-name \"socialnetwork-user-timeline-service-1\""
    echo "  --service-name-for-traces \"user-timeline-service\""
    echo "  --test-name \"Compose Post\""
    echo "  --config \"t12 c400 d300 R10\""
    echo "  --docker-compose-dir \"~/workspace/DeathStarBench/socialNetwork\""
}

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
        --service-name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --service-name-for-traces)
            SERVICE_NAME_FOR_TRACES="$2"
            shift 2
            ;;
        --test-name)
            TEST_NAME="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --docker-compose-dir)
            DOCKER_COMPOSE_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$SERVICE_NAME" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DOCKER_COMPOSE_DIR" ]]; then
    usage
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"
DATA_DIR="$(realpath "$SCRIPTS_DIR/../data")"

curr_time=$(date +"%Y-%m-%d_%H-%M-%S")
echo "Started at: $curr_time"
echo -e "\nSCRIPTS_DIR: $SCRIPTS_DIR"
echo "SRC_DIR: $SRC_DIR"
echo -e "DATA_DIR: $DATA_DIR \n"

make_dirs $curr_time

echo -e "\n--------------------------------------------------"
echo "Running deathstar_clean_start.sh"
$SCRIPTS_DIR/deathstar_clean_start.sh --docker_compose_dir "$DOCKER_COMPOSE_DIR" || exit 1
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running get_pid_info_for_containers.sh"
$SCRIPTS_DIR/get_pid_info_for_containers.sh || exit 1
echo -e "--------------------------------------------------\n"

echo "sleep 5"
sleep 5

echo "--------------------------------------------------"
echo "Running run_workload.sh in background"
$SCRIPTS_DIR/run_workload.sh --docker_compose_dir "$DOCKER_COMPOSE_DIR" --service_name "$SERVICE_NAME" --test_name "$TEST_NAME" --config "$CONFIG" > "$DATA_DIR/$curr_time/run_workload_output.log" 2>&1 &
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running collect_perf_data.sh"
$SCRIPTS_DIR/collect_perf_data.sh --service_name "$SERVICE_NAME" --config "$CONFIG" --data_dir "$DATA_DIR/$curr_time/" || exit 1
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running collect_analyse_jaeger_traces.sh"
$SCRIPTS_DIR/collect_analyse_jaeger_traces.sh --service_name "$SERVICE_NAME" --limit 1 --data_dir "$DATA_DIR/$curr_time/data" --src_dir "$SRC_DIR" || exit 1
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running plot_data.sh"
$SCRIPTS_DIR/plot_data.sh --test_name "$TEST_NAME" --service_name "$SERVICE_NAME" --config "$CONFIG" --data_dir "$DATA_DIR/$curr_time" --src_dir "$SRC_DIR" || exit 1
echo "--------------------------------------------------"