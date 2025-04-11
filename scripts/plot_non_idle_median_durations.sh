#!/bin/bash

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(realpath "$SCRIPTS_DIR/..")"
PROFILE_SRC_DIR="$BASE_DIR/src/profile"
MEDIAN_DURATIONS_DATA_DIR="$BASE_DIR/non_idle_median_durations/data"
MEDIAN_DURATIONS_PLOT_DIR="$BASE_DIR/non_idle_median_durations/plots"

echo "SCRIPTS_DIR: $SCRIPTS_DIR"
echo "BASE_DIR: $BASE_DIR"
echo "PROFILE_SRC_DIR: $PROFILE_SRC_DIR"
echo "MEDIAN_DURATIONS_DATA_DIR: $MEDIAN_DURATIONS_DATA_DIR"
echo "MEDIAN_DURATIONS_PLOT_DIR: $MEDIAN_DURATIONS_PLOT_DIR"

if [ ! -d "$MEDIAN_DURATIONS_DATA_DIR" ]; then
  echo "Error: Directory $MEDIAN_DURATIONS_DATA_DIR does not exist."
  exit 1
fi

echo "mkdir -p $MEDIAN_DURATIONS_PLOT_DIR"
mkdir -p "$MEDIAN_DURATIONS_PLOT_DIR"

echo "python3 $SCRIPTS_DIR/plot_non_idle_median_durations.py --data-dir $MEDIAN_DURATIONS_DATA_DIR --plot-dir $MEDIAN_DURATIONS_PLOT_DIR"
python3 "$SCRIPTS_DIR/plot_non_idle_median_durations.py" --data-dir "$MEDIAN_DURATIONS_DATA_DIR" --plot-dir "$MEDIAN_DURATIONS_PLOT_DIR" || {
    echo "Error: Failed to create non-idle median durations plots."
    exit 1
}
