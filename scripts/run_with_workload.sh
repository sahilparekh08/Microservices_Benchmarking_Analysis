#!/bin/bash

# TODO: 
# multiple cores
# runtime for 100, 1000 requests on same amount of cores
# more csv data for time vs instructions / llc data for every req like in the median processing
# check on the workload gen params
# remove the non execution times in the trace perf plot and check the instructions, llc graphs for the non overlapping exec times for each req, basically when the exec is waiting, dont consider that time interval in the plot

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
CORE_TO_PIN_PROFILER=""
TARGET_CORE=""

usage() {    
    echo "Usage: $0 [args]"
    echo "Arg examples:"
    echo "  --container-name \"socialnetwork-user-timeline-service-1\""
    echo "  --service-name-for-traces \"user-timeline-service\""
    echo "  --test-name \"Compose Post\""
    echo "  --config \"t12 c400 d300 R10 cp2\""
    echo "  --docker-compose-dir \"~/workspace/DeathStarBench/socialNetwork\""
    echo "  --core-to-pin-profiler 6"
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

    echo "mkdir -p $DATA_DIR/workload/$curr_time/data/traces"
    mkdir -p $DATA_DIR/workload/$curr_time/data/traces

    echo "mkdir -p $DATA_DIR/workload/$curr_time/data/profile_data"
    mkdir -p $DATA_DIR/workload/$curr_time/data/profile_data

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

    DOCKER_CONTAINER_SERVICE_CONFIG_PATH="$DATA_DIR/docker_container_service_config.csv"
    if [ -f "$DOCKER_CONTAINER_SERVICE_CONFIG_PATH" ]; then
        echo "rm $DOCKER_CONTAINER_SERVICE_CONFIG_PATH"
        rm "$DOCKER_CONTAINER_SERVICE_CONFIG_PATH"
    fi

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
        --core-to-pin-profiler)
            CORE_TO_PIN_PROFILER="$2"
            shift 2
            ;;
        --core-to-profile)
            TARGET_CORE="$2"
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

if [[ -z "$CONTAINER_NAME" || -z "$SERVICE_NAME_FOR_TRACES" || -z "$TEST_NAME" || -z "$CONFIG" || -z "$DOCKER_COMPOSE_DIR" || -z "$CORE_TO_PIN_PROFILER" || -z "$TARGET_CORE" ]]; then
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
echo "CORE_TO_PIN_PROFILER: $CORE_TO_PIN_PROFILER"
echo -e "TARGET_CORE: $TARGET_CORE\n"

make_dirs $curr_time

DATA_DIR_PARENT="$DATA_DIR"
DATA_DIR="$DATA_DIR/workload/$curr_time"
echo -e "\nNew DATA_DIR: $DATA_DIR"

echo "chmod +x $SCRIPTS_DIR/*"
chmod +x $SCRIPTS_DIR/*

echo -e "\n--------------------------------------------------"
echo "Running deathstar_clean_start.sh"
$SCRIPTS_DIR/deathstar_clean_start.sh --docker-compose-dir "$DOCKER_COMPOSE_DIR" --log-dir "$LOG_DIR" || {
    echo "Failed to bring up docker compose"
    exit 1
}
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running get_pid_info_for_containers.sh"
$SCRIPTS_DIR/get_pid_info_for_containers.sh || {
    echo "Failed to get PID info for containers"
    exit 1
}
echo -e "--------------------------------------------------\n"

echo "sleep 5"
sleep 5

echo -e "\n--------------------------------------------------"
# NOTE: Edit grub file to specific isolcpus=<cpu_to_pin_profiler>,<cpu_to_profile> for the container to profile and then reboot
RUN_WORKLOAD_ON_LOCAL_LOG_PATH="$LOG_DIR/run_workload_on_local_output.log"
echo "Running execute_workload_on_local.sh in background with logs saved at $RUN_WORKLOAD_ON_LOCAL_LOG_PATH"
$SCRIPTS_DIR/execute_workload_on_local.sh --docker-compose-dir "$DOCKER_COMPOSE_DIR" --test-name "$TEST_NAME" --config "$CONFIG" > "$RUN_WORKLOAD_ON_LOCAL_LOG_PATH" 2>&1 &
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running profile_core.sh"
$SCRIPTS_DIR/profile_core.sh --core-to-pin "$CORE_TO_PIN_PROFILER" --target-cores "$TARGET_CORE" --config "$CONFIG" --data-dir "$DATA_DIR" || {
    echo "Failed to profile core"
    exit 1
}
echo -e "--------------------------------------------------\n"

echo "sleep 5"
sleep 5

echo -e "\n(cd \"$DOCKER_COMPOSE_DIR\" && docker compose ps | awk '{print \$1 \",\" \$4}' > \"$DATA_DIR/docker_container_service_config.csv\")"
(cd "$DOCKER_COMPOSE_DIR" && docker compose ps | awk '{print $1 "," $4}' > "$DATA_DIR/docker_container_service_config.csv")

echo -e "\n--------------------------------------------------"
echo "Running collect_analyse_jaeger_traces.sh"

CMD="$SCRIPTS_DIR/collect_analyse_jaeger_traces.sh"
CMD="$CMD --test-name $TEST_NAME"
CMD="$CMD --config $CONFIG"
CMD="$CMD --service-name-for-traces $SERVICE_NAME_FOR_TRACES"
CMD="$CMD --limit $JAEGER_TRACES_LIMIT"
CMD="$CMD --data-dir $DATA_DIR"

if $SAVE_TRACES_JSON; then
    CMD="$CMD --save-traces-json"
fi

echo "Running command: $CMD"
$CMD || {
    echo "Failed to collect and analyse Jaeger traces"
    exit 1
}
echo -e "--------------------------------------------------\n"

echo "--------------------------------------------------"
echo "Running plot_data.sh"
$SCRIPTS_DIR/plot_data.sh --test-name "$TEST_NAME" --container-name "$CONTAINER_NAME" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --config "$CONFIG" --data-dir "$DATA_DIR" || {
    echo "Failed to plot data"
    exit 1
}
echo "--------------------------------------------------"
