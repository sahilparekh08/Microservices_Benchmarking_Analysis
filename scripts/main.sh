#!/bin/bash

CURR_USER="$(whoami)"

if [ "$EUID" -ne 0 ]; then
    echo "$0 must be run as root... Re-running with sudo"
    echo -e "sudo $0 \"$@\" --user $CURR_USER\n"
    sudo $0 "$@" --user $CURR_USER
    exit
fi

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
    exit 1
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

    echo "mkdir -p $LOG_DIR"
    mkdir -p $LOG_DIR
}

cleanup() {
    if [ -z "$DATA_DIR" ]; then
        return
    fi

    echo -e "\nchown -R $CURR_USER:$CURR_USER $DATA_DIR"
    chown -R $CURR_USER:$CURR_USER $DATA_DIR

    echo -e "\nFinished at: $(date +"%Y-%m-%d_%H-%M-%S")"
}

trap cleanup EXIT

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
        --user)
            CURR_USER="$2"
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
fi

curr_time=$(date +"%Y-%m-%d_%H-%M-%S")

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"
DATA_DIR="$(realpath "$SCRIPTS_DIR/../data")"
LOG_DIR="$DATA_DIR/$curr_time/logs"

echo "Started at: $curr_time"
echo -e "\nSCRIPTS_DIR: $SCRIPTS_DIR"
echo "SRC_DIR: $SRC_DIR"
echo "DATA_DIR: $DATA_DIR"
echo "LOG_DIR: $LOG_DIR"

echo -e "\nSERVICE_NAME: $SERVICE_NAME"
echo "SERVICE_NAME_FOR_TRACES: $SERVICE_NAME_FOR_TRACES"
echo "TEST_NAME: $TEST_NAME"
echo "CONFIG: $CONFIG"
echo -e "DOCKER_COMPOSE_DIR: $DOCKER_COMPOSE_DIR\n"

make_dirs $curr_time

DATA_DIR="$DATA_DIR/$curr_time"
echo -e "\nNew DATA_DIR: $DATA_DIR"

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

echo -e "\n--------------------------------------------------"
RUN_WORKLOAD_ON_LOCAL_LOG_PATH="$LOG_DIR/run_workload_on_local_output.log"
echo "Running run_workload_on_local.sh in background with logs saved at $RUN_WORKLOAD_ON_LOCAL_LOG_PATH"
$SCRIPTS_DIR/run_workload_on_local.sh --docker_compose_dir "$DOCKER_COMPOSE_DIR" --service-name "$SERVICE_NAME" --test-name "$TEST_NAME" --config "$CONFIG" > "$RUN_WORKLOAD_ON_LOCAL_LOG_PATH" 2>&1 &
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running collect_perf_data.sh"
$SCRIPTS_DIR/collect_perf_data.sh --service-name "$SERVICE_NAME" --config "$CONFIG" --data-dir "$DATA_DIR" || exit 1
echo -e "--------------------------------------------------\n"

echo "sleep 5"
sleep 5

echo -e "\n--------------------------------------------------"
echo "Running collect_analyse_jaeger_traces.sh"
$SCRIPTS_DIR/collect_analyse_jaeger_traces.sh --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --limit 1 --data-dir "$DATA_DIR" --src-dir "$SRC_DIR" || exit 1
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running plot_data.sh"
$SCRIPTS_DIR/plot_data.sh --test-name "$TEST_NAME" --service-name "$SERVICE_NAME" --config "$CONFIG" --data-dir "$DATA_DIR" --src-dir "$SRC_DIR" || exit 1
echo "--------------------------------------------------"
