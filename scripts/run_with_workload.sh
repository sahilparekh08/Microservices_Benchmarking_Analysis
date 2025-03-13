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
TEST_NAME=""
CONFIG=""
DOCKER_COMPOSE_DIR=""
JAEGER_TRACES_LIMIT=1
SAVE_TRACES_JSON=false
DATA_DIR_PARENT=""
CORE=""

usage() {    
    echo "Usage: $0 [args]"
    echo "Arg examples:"
    echo "  --container-name \"socialnetwork-user-timeline-service-1\""
    echo "  --service-name-for-traces \"user-timeline-service\""
    echo "  --test-name \"Compose Post\""
    echo "  --config \"t12 c400 d300 R10 cp2\""
    echo "  --docker-compose-dir \"~/workspace/DeathStarBench/socialNetwork\""
    echo "  --core-to-profile 7"
    echo "Optional args:"
    echo "  --jaeger-traces-limit 100"
    echo "  --save-traces-json"
    exit 1
}

make_dirs() {
    curr_time=$1
    
    echo "mkdir -p $DATA_DIR"
    mkdir -p $DATA_DIR

    echo "mkdir -p $DATA_DIR/workload"
    mkdir -p $DATA_DIR/workload

    echo "mkdir -p $DATA_DIR/workload/$curr_time"
    mkdir -p $DATA_DIR/workload/$curr_time

    echo "mkdir -p $DATA_DIR/workload/$curr_time/data"
    mkdir -p $DATA_DIR/workload/$curr_time/data

    echo "mkdir -p $DATA_DIR/workload/$curr_time/plots"
    mkdir -p $DATA_DIR/workload/$curr_time/plots

    echo "mkdir -p $DATA_DIR/workload/$curr_time/plots/traces"
    mkdir -p $DATA_DIR/workload/$curr_time/plots/traces

    echo "mkdir -p $DATA_DIR/workload/$curr_time/plots/perf"
    mkdir -p $DATA_DIR/workload/$curr_time/plots/perf

    echo "mkdir -p $DATA_DIR/workload/$curr_time/plots/perf_with_traces"
    mkdir -p $DATA_DIR/workload/$curr_time/plots/perf_with_traces

    echo "mkdir -p $LOG_DIR"
    mkdir -p $LOG_DIR
}

cleanup() {
    if [ -z "$DATA_DIR" ]; then
        return
    fi

    echo "rm $DATA_DIR/docker_container_service_config.csv"
    rm "$DATA_DIR/docker_container_service_config.csv"

    echo -e "\nchown -R $CURR_USER:$CURR_USER $DATA_DIR_PARENT"
    chown -R $CURR_USER:$CURR_USER $DATA_DIR_PARENT

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
        --core-to-profile)
            CORE="$2"
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

if [[ -z "$CONTAINER_NAME" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DOCKER_COMPOSE_DIR" || -z "$CORE" ]]; then
    usage
fi

curr_time=$(date +"%Y-%m-%d_%H-%M-%S")

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATA_DIR="$(realpath "$SCRIPTS_DIR/../data")"
LOG_DIR="$DATA_DIR/workload/$curr_time/logs"

echo "Started at: $curr_time"
echo -e "\nSCRIPTS_DIR: $SCRIPTS_DIR"
echo "DATA_DIR: $DATA_DIR"
echo "LOG_DIR: $LOG_DIR"

echo -e "\nCONTAINER_NAME: $CONTAINER_NAME"
echo "SERVICE_NAME_FOR_TRACES: $SERVICE_NAME_FOR_TRACES"
echo "TEST_NAME: $TEST_NAME"
echo "CONFIG: $CONFIG"
echo "DOCKER_COMPOSE_DIR: $DOCKER_COMPOSE_DIR"
echo -e "CORE: $CORE\n"

make_dirs $curr_time

DATA_DIR_PARENT="$DATA_DIR"
DATA_DIR="$DATA_DIR/workload/$curr_time"
echo -e "\nNew DATA_DIR: $DATA_DIR"

echo "chmod +x $SCRIPTS_DIR/*"
chmod +x $SCRIPTS_DIR/*

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

echo -e "\n--------------------------------------------------"
# NOTE: Edit grub file to specific isolcpus=<cpu number> for the container to profile and then reboot
RUN_WORKLOAD_ON_LOCAL_LOG_PATH="$LOG_DIR/run_workload_on_local_output.log"
echo "Running execute_workload_on_local.sh in background with logs saved at $RUN_WORKLOAD_ON_LOCAL_LOG_PATH"
$SCRIPTS_DIR/execute_workload_on_local.sh --docker-compose-dir "$DOCKER_COMPOSE_DIR" --test-name "$TEST_NAME" --config "$CONFIG" > "$RUN_WORKLOAD_ON_LOCAL_LOG_PATH" 2>&1 &
echo -e "--------------------------------------------------\n"

# echo "--------------------------------------------------"
# echo "Running collect_perf_data.sh"
# $SCRIPTS_DIR/collect_perf_data.sh --container-name "$CONTAINER_NAME" --config "$CONFIG" --data-dir "$DATA_DIR" || exit 1
# echo -e "--------------------------------------------------\n"

# echo "--------------------------------------------------"
# echo "Running profile_core_assembly.sh"
# $SCRIPTS_DIR/profile_core_assembly.sh --core $CORE --config "$CONFIG" --data-dir "$DATA_DIR" || exit 1
# echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running profile_core.sh"
$SCRIPTS_DIR/profile_core.sh --core $CORE --config "$CONFIG" --data-dir "$DATA_DIR" || exit 1
echo "--------------------------------------------------"

echo "sleep 5"
sleep 5

echo -e "\n(cd \"$DOCKER_COMPOSE_DIR\" && docker compose ps | awk '{print \$1 \",\" \$4}' > \"$DATA_DIR/docker_container_service_config.csv\")"
(cd "$DOCKER_COMPOSE_DIR" && docker compose ps | awk '{print $1 "," $4}' > "$DATA_DIR/docker_container_service_config.csv")

echo -e "\n--------------------------------------------------"
echo "Running collect_analyse_jaeger_traces.sh"
if $SAVE_TRACES_JSON; then
    $SCRIPTS_DIR/collect_analyse_jaeger_traces.sh --test-name "$TEST_NAME" --config "$CONFIG" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --limit $JAEGER_TRACES_LIMIT --data-dir "$DATA_DIR" --save-traces-json || exit 1
else 
    $SCRIPTS_DIR/collect_analyse_jaeger_traces.sh --test-name "$TEST_NAME" --config "$CONFIG" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --limit $JAEGER_TRACES_LIMIT --data-dir "$DATA_DIR" || exit 1
fi
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running plot_data.sh"
$SCRIPTS_DIR/plot_data.sh --test-name "$TEST_NAME" --container-name "$CONTAINER_NAME" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --config "$CONFIG" --data-dir "$DATA_DIR" || exit 1
echo "--------------------------------------------------"
