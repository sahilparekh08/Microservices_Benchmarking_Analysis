#!/bin/bash

if [[ $# -lt 1 ]]; then
	echo "Usage: docker_clean_start <DOCKER_COMPOSE_DIR_PATH>"
	exit 1
fi

DOCKER_COMPOSE_DIR_PATH="$(realpath "$1")"
CURR_DIR="$(pwd)"

echo "cd $DOCKER_COMPOSE_DIR_PATH || exit 1"
cd $DOCKER_COMPOSE_DIR_PATH || exit 1

echo "docker compose down || exit 1"
docker compose down || exit 1

echo "docker volume prune -f"
docker volume prune -f

echo "docker compose up -d || exit 1"
docker compose up -d || exit 1

if [[ "$DOCKER_COMPOSE_DIR_PATH" =~ socialNetwork$ ]]; then
	echo "python3 scripts/init_social_graph.py --graph=socfb-Reed98"
	python3 scripts/init_social_graph.py --graph=socfb-Reed98
fi

echo "cd $CURR_DIR || exit 1"
cd $CURR_DIR || exit 1
