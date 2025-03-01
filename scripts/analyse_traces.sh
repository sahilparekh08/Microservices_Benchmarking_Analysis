#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Usage: $0 <service_name>"
    exit 1
fi

SERVICE_NAME=$1
SRC_DIR="$(cd "$(dirname "$0")"/.. && pwd)/src"
DATA_DIR="$(cd "$(dirname "$0")"/.. && pwd)/data"

mkdir -p "$DATA_DIR"

python3 "$SRC_DIR/main.py" "$SERVICE_NAME" "$DATA_DIR"
