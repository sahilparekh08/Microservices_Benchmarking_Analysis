#!/bin/bash

DOCKER_COMPOSE_DIR=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--docker-compose-dir)
			DOCKER_COMPOSE_DIR="$2"
			shift 2
			;;
		*)
			echo "Unknown option: $1"
			exit 1
			;;
	esac
done

if [[ -z "$DOCKER_COMPOSE_DIR" ]]; then
	echo "Usage: docker_clean_start --docker_compose_dir <DOCKER_COMPOSE_DIR>"
	exit 1
fi

if [[ ! -d "$DOCKER_COMPOSE_DIR" ]]; then
	echo "Directory $DOCKER_COMPOSE_DIR does not exist"
	exit 1
fi

echo "(cd \"$DOCKER_COMPOSE_DIR\" && docker compose down)"
(cd "$DOCKER_COMPOSE_DIR" && docker compose down) || {
	echo "Failed to bring down docker compose"
	exit 1
}

echo -e "\ndocker volume prune -f"
docker volume prune -f
