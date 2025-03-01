#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Usage: $0 <service_name> <traces_limit> <data_dir> [<src_dir>]"
    exit 1
fi

SERVICE_NAME=$1
LIMIT=$2
DATA_DIR=$3
SRC_DIR=${4:-"$(cd "$(dirname "$0")"/.. && pwd)/src"}

python3 "$SRC_DIR/analyse_jaeger_traces.py" "$SERVICE_NAME" "$DATA_DIR" "$LIMIT"
