#!/bin/bash

TEST_NAME=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --test-name)
      TEST_NAME="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

TEST_NAME=${TEST_NAME// /_}

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(realpath "$SCRIPTS_DIR/..")"
PROFILE_SRC_DIR="$BASE_DIR/src/profile"
NON_IDLE_DURATIONS_DATA_DIR="$BASE_DIR/non_idle_durations/data/$TEST_NAME"
NON_IDLE_DURATIONS_PLOT_DIR="$BASE_DIR/non_idle_durations/plots/"
NON_IDLE_DURATIONS_TEST_PLOT_DIR="$BASE_DIR/non_idle_durations/plots/$TEST_NAME"

echo "TEST_NAME: $TEST_NAME"
echo "SCRIPTS_DIR: $SCRIPTS_DIR"
echo "BASE_DIR: $BASE_DIR"
echo "PROFILE_SRC_DIR: $PROFILE_SRC_DIR"
echo "NON_IDLE_DURATIONS_DATA_DIR: $NON_IDLE_DURATIONS_DATA_DIR"
echo "NON_IDLE_DURATIONS_PLOT_DIR: $NON_IDLE_DURATIONS_PLOT_DIR"

if [ ! -d "$NON_IDLE_DURATIONS_DATA_DIR" ]; then
  echo "Error: Directory $NON_IDLE_DURATIONS_DATA_DIR does not exist."
  exit 1
fi

echo -e "\nmkdir -p $NON_IDLE_DURATIONS_PLOT_DIR"
mkdir -p "$NON_IDLE_DURATIONS_PLOT_DIR"
echo "mkdir -p $NON_IDLE_DURATIONS_TEST_PLOT_DIR"
mkdir -p "$NON_IDLE_DURATIONS_TEST_PLOT_DIR"

echo -e "\npython3 $PROFILE_SRC_DIR/plot_non_idle_durations.py --data-dir $NON_IDLE_DURATIONS_DATA_DIR --plot-dir $NON_IDLE_DURATIONS_TEST_PLOT_DIR"
python3 "$PROFILE_SRC_DIR/plot_non_idle_durations.py" --data-dir "$NON_IDLE_DURATIONS_DATA_DIR" --plot-dir "$NON_IDLE_DURATIONS_TEST_PLOT_DIR" || {
    echo "Error: Failed to create non-idle median durations plots."
    exit 1
}
