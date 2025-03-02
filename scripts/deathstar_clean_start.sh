#!/bin/bash

DOCKER_COMPOSE_DIR=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--docker_compose_dir)
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

echo "(cd \"$DOCKER_COMPOSE_DIR\" && docker compose down) || exit 1"
(cd "$DOCKER_COMPOSE_DIR" && docker compose down) || exit 1

echo "docker volume prune -f"
docker volume prune -f

echo "(cd \"$DOCKER_COMPOSE_DIR\" && docker compose up -d) || exit 1"
(cd "$DOCKER_COMPOSE_DIR" && docker compose up -d) || exit 1

if [[ "$DOCKER_COMPOSE_DIR" =~ socialNetwork$ ]]; then
	echo "python3 $DOCKER_COMPOSE_DIR/scripts/init_social_graph.py --graph=socfb-Reed98"
	python3 $DOCKER_COMPOSE_DIR/scripts/init_social_graph.py --graph=socfb-Reed98
fi
