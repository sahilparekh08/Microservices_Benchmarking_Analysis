#!/bin/bash

DOCKER_COMPOSE__DIR_PATH=""
TEST_NAME=""
CONFIG=""

usage() {
    echo "Usage: $0 --docker_compose_dir <docker_compose_dir> --test-name <test_name> --config <config>"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker_compose_dir)
            DOCKER_COMPOSE__DIR_PATH="$2"
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
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check required arguments
if [[ -z "$DOCKER_COMPOSE__DIR_PATH" || -z "$TEST_NAME" || -z "$CONFIG" ]]; then
    usage
fi

# Parse config parameters
THREADS=0
CLIENTS=0
DURATION=0
RATE=0

IFS=' ' read -r -a CONFIG <<< "$CONFIG"
for i in "${CONFIG[@]}"; do
    case "$i" in
        t*)
            THREADS="${i:1}"
            ;;
        cp*)
            echo "Cache partitions: ${i:2}"
            ;;
        c*)
            CLIENTS="${i:1}"
            ;;
        d*)
            DURATION="${i:1}"
            ;;
        R*)
            RATE="${i:1}"
            ;;
        *)
            echo "Unknown option: $i"
            exit 1
            ;;
    esac
done

# Validate config parameters
if [[ $THREADS -eq 0 || $CLIENTS -eq 0 || $DURATION -eq 0 || $RATE -eq 0 ]]; then
    echo "Invalid config: $CONFIG"
    usage
fi

# Wait for services to be ready
echo "Waiting for services to be ready..."
echo "Command: sleep 1"
sleep 1

# Execute workload based on service and test name
if [[ "$(basename "$DOCKER_COMPOSE__DIR_PATH")" == "socialNetwork" ]]; then
    echo -e "\nWorkload started at $(date)\n"

    if [[ "$TEST_NAME" == "Compose Post" ]]; then
        echo "Command: $DOCKER_COMPOSE__DIR_PATH/../wrk2/wrk -D exp -t $THREADS -c $CLIENTS -d $DURATION -L -s $DOCKER_COMPOSE__DIR_PATH/wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R $RATE"
        $DOCKER_COMPOSE__DIR_PATH/../wrk2/wrk -D exp -t $THREADS -c $CLIENTS -d $DURATION -L -s $DOCKER_COMPOSE__DIR_PATH/wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R $RATE
    elif [[ "$TEST_NAME" == "Read Home Timeline" ]]; then
        echo "Command: $DOCKER_COMPOSE__DIR_PATH/../wrk2/wrk -D exp -t $THREADS -c $CLIENTS -d $DURATION -L -s $DOCKER_COMPOSE__DIR_PATH/wrk2/scripts/social-network/read-home-timeline.lua http://localhost:8080/wrk2-api/home-timeline/read -R $RATE"
        $DOCKER_COMPOSE__DIR_PATH/../wrk2/wrk -D exp -t $THREADS -c $CLIENTS -d $DURATION -L -s $DOCKER_COMPOSE__DIR_PATH/wrk2/scripts/social-network/read-home-timeline.lua http://localhost:8080/wrk2-api/home-timeline/read -R $RATE
    else
        echo "Unknown test name: $TEST_NAME"
        exit 1
    fi

    echo -e "\nWorkload finished at $(date)"
else
    echo "Unknown service name: $DOCKER_COMPOSE__DIR_PATH"
    exit 1
fi