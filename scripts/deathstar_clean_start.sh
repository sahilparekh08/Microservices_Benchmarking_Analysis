#!/bin/bash

# Parse command line arguments
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

# Check required arguments
if [[ -z "$DOCKER_COMPOSE_DIR" ]]; then
	echo "Usage: $0 --docker-compose-dir <docker_compose_dir> [--log-dir <log_dir>]"
	exit 1
fi

# Check if directory exists
if [[ ! -d "$DOCKER_COMPOSE_DIR" ]]; then
	echo "Directory $DOCKER_COMPOSE_DIR does not exist"
	exit 1
fi

# Bring down docker compose
echo "Bringing down docker compose..."
echo "Command: (cd \"$DOCKER_COMPOSE_DIR\" && docker compose down)"
(cd "$DOCKER_COMPOSE_DIR" && docker compose down) || {
	echo "Failed to bring down docker compose"
	exit 1
}

# Clean up docker volumes
echo -e "\nCleaning up docker volumes..."
echo "Command: docker volume prune -f"
docker volume prune -f

# Bring up docker compose
echo -e "\nBringing up docker compose..."
echo "Command: (cd \"$DOCKER_COMPOSE_DIR\" && docker compose up -d)"
(cd "$DOCKER_COMPOSE_DIR" && docker compose up -d) || {
	echo "Failed to bring up docker compose"
	exit 1
}

# Initialize social graph if needed
if [[ "$(basename "$DOCKER_COMPOSE_DIR")" = "socialNetwork" ]]; then
	echo -e "\nInitializing social graph..."
	if [[ -z "$LOG_DIR" ]]; then
		echo "Command: (cd \"$DOCKER_COMPOSE_DIR\" && python3 \"scripts/init_social_graph.py\" --graph=socfb-Reed98)"
		(cd "$DOCKER_COMPOSE_DIR" && python3 "scripts/init_social_graph.py" --graph=socfb-Reed98)
	else
		echo "Command: (cd \"$DOCKER_COMPOSE_DIR\" && python3 \"scripts/init_social_graph.py\" --graph=socfb-Reed98) > \"$LOG_DIR/init_social_graph.log\" 2>&1"
		(cd "$DOCKER_COMPOSE_DIR" && python3 "scripts/init_social_graph.py" --graph=socfb-Reed98) > "$LOG_DIR/init_social_graph.log" 2>&1
	fi
fi

