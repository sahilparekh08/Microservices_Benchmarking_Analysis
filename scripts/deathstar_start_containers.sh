#!/bin/bash

DOCKER_COMPOSE_DIR=""
LOG_DIR=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--docker-compose-dir)
			DOCKER_COMPOSE_DIR="$2"
			shift 2
			;;
		--log-dir)
			LOG_DIR="$2"
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

echo -e "\n(cd \"$DOCKER_COMPOSE_DIR\" && docker compose up -d)"
(cd "$DOCKER_COMPOSE_DIR" && docker compose up -d) || {
	echo "Failed to bring up docker compose"
	exit 1
}

if [[ "$(basename "$DOCKER_COMPOSE_DIR")" = "socialNetwork" ]]; then
	if [[ -z "$LOG_DIR" ]]; then
		echo -e "\n(cd \"$DOCKER_COMPOSE_DIR\" && python3 \"scripts/init_social_graph.py\" --graph=socfb-Reed98)"
		(cd "$DOCKER_COMPOSE_DIR" && python3 "scripts/init_social_graph.py" --graph=socfb-Reed98)
	else
		echo -e "\n(cd \"$DOCKER_COMPOSE_DIR\" && python3 \"scripts/init_social_graph.py\" --graph=socfb-Reed98) > \"$LOG_DIR/init_social_graph.log\" 2>&1"
		(cd "$DOCKER_COMPOSE_DIR" && python3 "scripts/init_social_graph.py" --graph=socfb-Reed98) > "$LOG_DIR/init_social_graph.log" 2>&1
	fi
fi

