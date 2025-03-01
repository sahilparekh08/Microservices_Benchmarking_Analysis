#!/bin/bash

if [[ $# -lt 4 ]]; then
    echo "Usage: $0 <TEST_NAME> <SERVICE_NAME> <CONFIG> <DATA_DIR> [<SRC_DIR>]"
    exit 1
fi

TEST_NAME="$1"
SERVICE_NAME="$2"
CONFIG="$3"
DATA_DIR="$4"
SRC_DIR="${5:-"$(cd "$(dirname "$0")"/.. && pwd)/src"}"

echo "python3 $SRC_DIR/plot_llc_data.py \"${TEST_NAME}\" \"${SERVICE_NAME}\" \"${CONFIG}\" \"${DATA_DIR}\""
python3 $SRC_DIR/plot_llc_data.py "${TEST_NAME}" "${SERVICE_NAME}" "${CONFIG}" "${DATA_DIR}"

echo "python3 $SRC_DIR/plot_jaeger_data.py \"${TEST_NAME}\" \"${SERVICE_NAME}\" \"${CONFIG}\" \"${DATA_DIR}\""
python3 $SRC_DIR/plot_jaeger_data.py "${TEST_NAME}" "${SERVICE_NAME}" "${CONFIG}" "${DATA_DIR}"