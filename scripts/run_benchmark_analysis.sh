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
CORE_TO_PIN_PROFILER=""
TARGET_CORES=""
COS=""
NON_IDLE_DURATION_ONLY_MODE=false
NUM_RUNS=1

usage() {    
    echo "Usage: $0 [args]"
    echo "Arg examples:"
    echo "  --container-name \"socialnetwork-user-timeline-service-1\""
    echo "  --service-name-for-traces \"user-timeline-service\""
    echo "  --test-name \"Compose Post\""
    echo "  --config \"t12 c400 d300 R10 cp2\""
    echo "  --docker-compose-dir \"~/workspace/DeathStarBench/socialNetwork\""
    echo "  --core-to-pin-profiler 5"
    echo "  --cores-to-profile 6,7"
    echo "  --cos 0,1,3"
    echo "Optional args:"
    echo "  --jaeger-traces-limit 100"
    echo "  --save-traces-json"
    echo "  --non-idle-duration-only-mode"
    echo "  --num-runs 100"
    exit 1
}

cleanup() {
    echo -e "\nchown -R $CURR_USER:$CURR_USER $BASE_DIR"
    chown -R $CURR_USER:$CURR_USER $BASE_DIR

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
        --cores-to-profile)
            TARGET_CORES="$2"
            shift 2
            ;;
        --cos)
            COS="$2"
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
        --non-idle-duration-only-mode)
            NON_IDLE_DURATION_ONLY_MODE=true
            shift
            ;;
        --num-runs)
            NUM_RUNS="$2"
            shift 2
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

if [[ ! "$NUM_RUNS" =~ ^[0-9]+$ ]] || [ "$NUM_RUNS" -le 0 ]; then
    echo "Invalid NUM_RUNS: $NUM_RUNS. It should be a positive integer."
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(dirname "$SCRIPTS_DIR")"
DATA_DIR="$BASE_DIR/data"
LOG_DIR="$DATA_DIR/logs"
mkdir -p "$DATA_DIR" "$LOG_DIR"

echo "Running workload with NUM_RUNS: $NUM_RUNS"
echo -e "Running  $SCRIPTS_DIR/run_with_workload.sh \\
    --container-name \"$CONTAINER_NAME\" \\
    --service-name-for-traces \"$SERVICE_NAME_FOR_TRACES\" \\
    --test-name \"$TEST_NAME\" \\
    --config \"$CONFIG\" \\
    --docker-compose-dir \"$DOCKER_COMPOSE_DIR\" \\
    --core-to-pin-profiler \"$CORE_TO_PIN_PROFILER\" \\
    --cores-to-profile \"$TARGET_CORES\" \\
    --cos \"$COS\" \\
    --jaeger-traces-limit \"$JAEGER_TRACES_LIMIT\" \\
    --save-traces-json $SAVE_TRACES_JSON \\
    --non-idle-duration-only-mode $NON_IDLE_DURATION_ONLY_MODE\n"

CURR_RUN=0


while [ $CURR_RUN -lt $NUM_RUNS ]; do
    LOG_FILE_PATH="$LOG_DIR/${TEST_NAME// /_}_run_$((CURR_RUN + 1)).log"
    curr_time=$(date +"%Y-%m-%d_%H-%M-%S")
    echo -e "$curr_time\tStarting run [$((CURR_RUN + 1))/$NUM_RUNS]\tLogging to: $LOG_FILE_PATH"

    if [[ "$SAVE_TRACES_JSON" == "true" && "$NON_IDLE_DURATION_ONLY_MODE" == "true" ]]; then
        $SCRIPTS_DIR/run_with_workload.sh --container-name "$CONTAINER_NAME" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --test-name "$TEST_NAME" --config "$CONFIG" --docker-compose-dir "$DOCKER_COMPOSE_DIR" --core-to-pin-profiler "$CORE_TO_PIN_PROFILER" --cores-to-profile "$TARGET_CORES" --cos "$COS" --jaeger-traces-limit "$JAEGER_TRACES_LIMIT" --save-traces-json --non-idle-duration-only-mode > "$LOG_FILE_PATH" 2>&1 || {
            echo "Run $((CURR_RUN + 1)) failed. Exiting."
            exit 1
        }
    elif [[ "$SAVE_TRACES_JSON" == "true" ]]; then
        $SCRIPTS_DIR/run_with_workload.sh --container-name "$CONTAINER_NAME" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --test-name "$TEST_NAME" --config "$CONFIG" --docker-compose-dir "$DOCKER_COMPOSE_DIR" --core-to-pin-profiler "$CORE_TO_PIN_PROFILER" --cores-to-profile "$TARGET_CORES" --cos "$COS" --jaeger-traces-limit "$JAEGER_TRACES_LIMIT" --save-traces-json > "$LOG_FILE_PATH" 2>&1 || {
                echo "Run $((CURR_RUN + 1)) failed. Exiting."
                exit 1
            }
    elif [[ "$NON_IDLE_DURATION_ONLY_MODE" == "true" ]]; then
        $SCRIPTS_DIR/run_with_workload.sh --container-name "$CONTAINER_NAME" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --test-name "$TEST_NAME" --config "$CONFIG" --docker-compose-dir "$DOCKER_COMPOSE_DIR" --core-to-pin-profiler "$CORE_TO_PIN_PROFILER" --cores-to-profile "$TARGET_CORES" --cos "$COS" --jaeger-traces-limit "$JAEGER_TRACES_LIMIT" --non-idle-duration-only-mode > "$LOG_FILE_PATH" 2>&1 || {
            echo "Run $((CURR_RUN + 1)) failed. Exiting."
            exit 1
        }
    else 
        $SCRIPTS_DIR/run_with_workload.sh --container-name "$CONTAINER_NAME" --service-name-for-traces "$SERVICE_NAME_FOR_TRACES" --test-name "$TEST_NAME" --config "$CONFIG" --docker-compose-dir "$DOCKER_COMPOSE_DIR" --core-to-pin-profiler "$CORE_TO_PIN_PROFILER" --cores-to-profile "$TARGET_CORES" --cos "$COS" --jaeger-traces-limit "$JAEGER_TRACES_LIMIT" > "$LOG_FILE_PATH" 2>&1 || {
            echo "Run $((CURR_RUN + 1)) failed. Exiting."
            exit 1
        }
    fi

    sleep 2

    CURR_RUN=$((CURR_RUN + 1))
done
