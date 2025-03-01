#!/bin/bash

DOCKER_COMPOSE_DIR_PATH=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--docker_compose_dir)
			DOCKER_COMPOSE_DIR_PATH="$2"
			shift 2
			;;
		*)
			echo "Unknown option: $1"
			exit 1
			;;
	esac
done

if [[ -z "$DOCKER_COMPOSE_DIR_PATH" ]]; then
	echo "Usage: docker_clean_start --docker_compose_dir <docker_compose_dir_path>"
	exit 1
fi

if [[ ! -d "$DOCKER_COMPOSE_DIR_PATH" ]]; then
	echo "Directory $DOCKER_COMPOSE_DIR_PATH does not exist"
	exit 1
fi

CURR_DIR="$(pwd)"

echo "cd $DOCKER_COMPOSE_DIR_PATH || exit 1"
cd ""$DOCKER_COMPOSE_DIR_PATH" || exit 1

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
