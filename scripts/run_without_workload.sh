#!/bin/bash

CURR_USER="$(whoami)"

if [ "$EUID" -ne 0 ]; then
    echo "$0 must be run as root... Re-running with sudo"
    echo -e "sudo $0 \"$@\" --user $CURR_USER\n"
    sudo $0 "$@" --user $CURR_USER
    exit
fi

CONTAINER_NAME=""
SERVICE_NAME_FOR_TRACES=""
TEST_NAME="no_workload"
DOCKER_COMPOSE_DIR=""
JAEGER_TRACES_LIMIT=1
SAVE_TRACES_JSON=false

usage() {    
    echo "Usage: $0 [args]"
    echo "Arg examples:"
    echo "  --container-name \"socialnetwork-user-timeline-service-1\""
    echo "  --service-name-for-traces \"user-timeline-service\""
    echo "  --docker-compose-dir \"~/workspace/DeathStarBench/socialNetwork\""
    echo "Optional args:"
    echo "  --jaeger-traces-limit 100"
    echo "  --save-traces-json"
    echo "  --help"
    exit 1
}

make_dirs() {
    echo "mkdir -p $DATA_DIR"
    mkdir -p $DATA_DIR

    echo "mkdir -p $DATA_DIR/no_workload"
    mkdir -p $DATA_DIR/no_workload

    echo "mkdir -p $DATA_DIR/no_workload/data"
    mkdir -p $DATA_DIR/no_workload/data

    echo "mkdir -p $DATA_DIR/no_workload/plots"
    mkdir -p $DATA_DIR/no_workload/plots

    echo "mkdir -p $LOG_DIR"
    mkdir -p $LOG_DIR
}

cleanup() {
    if [ -z "$DATA_DIR" ]; then
        return
    fi

    echo "rm $DATA_DIR/docker_container_service_config.csv"
    rm "$DATA_DIR/docker_container_service_config.csv"

    echo -e "\nchown -R $CURR_USER:$CURR_USER $DATA_DIR"
    chown -R $CURR_USER:$CURR_USER $DATA_DIR

    echo -e "\nFinished at: $(date +"%Y-%m-%d_%H-%M-%S")"
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
    case "$1" in
        --container-name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --service-name-for-traces)
            SERVICE_NAME_FOR_TRACES="$2"
            shift 2
            ;;
        --docker-compose-dir)
            DOCKER_COMPOSE_DIR="$2"
            shift 2
            ;;
        --jaeger-traces-limit)
            JAEGER_TRACES_LIMIT="$2"
            shift 2
            ;;
        --save-traces-json)
            SAVE_TRACES_JSON=true
            shift
            ;;
        --user)
            CURR_USER="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$CONTAINER_NAME" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$DOCKER_COMPOSE_DIR" ]]; then
    usage
fi

TEST_NAME=${TEST_NAME:-"No Workload Test"}

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"
DATA_DIR="$(realpath "$SCRIPTS_DIR/../data")"
LOG_DIR="$DATA_DIR/no_workload/logs"

echo "Started at: $(date)"
echo -e "\nSCRIPTS_DIR: $SCRIPTS_DIR"
echo "SRC_DIR: $SRC_DIR"
echo "DATA_DIR: $DATA_DIR"
echo "LOG_DIR: $LOG_DIR"

echo -e "\nCONTAINER_NAME: $CONTAINER_NAME"
echo "SERVICE_NAME_FOR_TRACES: $SERVICE_NAME_FOR_TRACES"
echo "TEST_NAME: $TEST_NAME"
echo -e "DOCKER_COMPOSE_DIR: $DOCKER_COMPOSE_DIR\n"

make_dirs

DATA_DIR="$DATA_DIR/no_workload"
echo -e "\nNew DATA_DIR: $DATA_DIR"

echo -e "\n--------------------------------------------------"
echo "Running deathstar_clean_start.sh"
$SCRIPTS_DIR/deathstar_clean_start.sh --docker-compose-dir "$DOCKER_COMPOSE_DIR" --log-dir "$LOG_DIR" || exit 1
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running get_pid_info_for_containers.sh"
$SCRIPTS_DIR/get_pid_info_for_containers.sh || exit 1
echo -e "--------------------------------------------------\n"

echo "sleep 5"
sleep 5

read -p "Enter duration in seconds to run perf for: " DURATION
if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || [ "$DURATION" -le 0 ]; then
    echo "Error: Duration must be a positive integer."
    exit 1
fi
CONFIG="d$DURATION"
echo "CONFIG: $CONFIG"

echo -e "\n--------------------------------------------------"
echo "Running collect_perf_data.sh"
$SCRIPTS_DIR/collect_perf_data.sh --container-name "$CONTAINER_NAME" --config "$CONFIG" --data-dir "$DATA_DIR" || exit 1
echo -e "--------------------------------------------------\n"

echo "sleep 5"
sleep 5

echo "(cd \"$DOCKER_COMPOSE_DIR\" && docker compose ps | awk '{print \$1 \",\" \$4}' > \"$DATA_DIR/docker_container_service_config.csv\")"
(cd "$DOCKER_COMPOSE_DIR" && docker compose ps | awk '{print $1 "," $4}' > "$DATA_DIR/docker_container_service_config.csv")

echo -e "\n--------------------------------------------------"
echo "Running collect_analyse_jaeger_traces.sh"
if $SAVE_TRACES_JSON; then
    $SCRIPTS_DIR/collect_analyse_jaeger_traces.sh --test-name "$TEST_NAME" --config "$CONFIG" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --limit $JAEGER_TRACES_LIMIT --data-dir "$DATA_DIR" --src-dir "$SRC_DIR" --save-traces-json || exit 1
else 
    $SCRIPTS_DIR/collect_analyse_jaeger_traces.sh --test-name "$TEST_NAME" --config "$CONFIG" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --limit $JAEGER_TRACES_LIMIT --data-dir "$DATA_DIR" --src-dir "$SRC_DIR" || exit 1
fi
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running plot_data.sh"
$SCRIPTS_DIR/plot_data.sh --test-name "$TEST_NAME" --container-name "$CONTAINER_NAME" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --config "$CONFIG" --data-dir "$DATA_DIR" --src-dir "$SRC_DIR" || exit 1
echo "--------------------------------------------------"
