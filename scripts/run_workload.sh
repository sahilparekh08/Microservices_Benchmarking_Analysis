#!/bin/bash

DOCKER_COMPOSE__DIR_PATH=""
SERVICE_NAME=""
TEST_NAME=""
CONFIG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker_compose_dir)
            DOCKER_COMPOSE_DIR="$2"
            shift 2
            ;;
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
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$DOCKER_COMPOSE_DIR" || -z "$SERVICE_NAME" || -z "$TEST_NAME" || -z "$CONFIG" ]]; then
    echo "Usage: $0 --docker_compose_dir <docker_compose_dir> --service_name <service_name> --test_name <test_name> --config <config>"
    exit 1
fi

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

echo "sleep 2"
sleep 2

if [[ "$DOCKER_COMPOSE_DIR" =~ socialNetwork$ ]]; then
    if [[ "$TEST_NAME" == "Compose Post" ]]; then
        $DOCKER_COMPOSE__DIR_PATH/../wrk2/wrk -D exp -t $THREADS -c $CLIENTS -d $DURATION -L -s $DOCKER_COMPOSE__DIR_PATH//wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R $RATE
    elif [[ "$TEST_NAME" == "Read Home Timeline" ]]; then
        $DOCKER_COMPOSE__DIR_PATH/../wrk2/wrk -D exp -t $THREADS -c $CLIENTS -d $DURATION -L -s $DOCKER_COMPOSE__DIR_PATH//wrk2/scripts/social-network/read-home-timeline.lua http://localhost:8080/wrk2-api/home-timeline/read -R $RATE
    else
        echo "Unknown test name: $TEST_NAME"
        exit 1
    fi
else
    echo "Unknown service name: $DOCKER_COMPOSE_DIR"
    exit 1
fi