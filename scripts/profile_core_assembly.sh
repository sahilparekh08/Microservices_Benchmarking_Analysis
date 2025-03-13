#!/bin/bash

CORE=""
CONFIG=""
DATA_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --core)
            CORE="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$CORE" || -z "$CONFIG" || -z "$DATA_DIR" ]]; then
    echo "Usage: $0 --core <core> --config <config> --data-dir <data_dir>"
    exit 1
fi

DURATION=0

IFS=' ' read -r -a CONFIG <<< "$CONFIG"
for i in "${CONFIG[@]}"; do
    case "$i" in
        d*)
            DURATION="${i:1}"
            ;;
    esac
done

if [[ $DURATION -eq 0 ]]; then
    echo "Duration not provided in config"
    exit 1
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="${SRC_DIR:-$(realpath "$SCRIPTS_DIR/../src")}"
RAW_PROFILE_DATA_OUTPUT_PATH="${DATA_DIR}/data/profile_data.raw"
PROFILE_DATA_OUTPUT_PATH="${DATA_DIR}/data/profile_data.csv"

DURATION=$((DURATION + 2))

echo "nasm -f elf64 $SRC_DIR/profiler.asm -o $SRC_DIR/profiler.o || exit 1"
nasm -f elf64 $SRC_DIR/profiler.asm -o $SRC_DIR/profiler.o || exit 1

echo "ld -dynamic-linker /lib64/ld-linux-x86-64.so.2 $SRC_DIR/profiler.o -o $SRC_DIR/profiler" || exit 1
ld -dynamic-linker /lib64/ld-linux-x86-64.so.2 $SRC_DIR/profiler.o -o $SRC_DIR/profiler || exit 1

echo -e "\nStarting profiler at $(date)"
echo "sudo $SRC_DIR/profiler $CORE $DURATION $RAW_PROFILE_DATA_OUTPUT_PATH"
sudo $SRC_DIR/profiler $CORE $DURATION $RAW_PROFILE_DATA_OUTPUT_PATH
echo -e "Finished at $(date)\n"

echo "echo \"Time,LLC-loads,LLC-misses,Instructions\" > $PROFILE_DATA_OUTPUT_PATH"
echo "Time,LLC-loads,LLC-misses,Instructions" > "$PROFILE_DATA_OUTPUT_PATH"

echo "hexdump -v -e '1/8 \"%u,\" 1/8 \"%u,\" 1/8 \"%u,\" 1/8 \"%u\n\"' \"$RAW_PROFILE_DATA_OUTPUT_PATH\" >> \"$PROFILE_DATA_OUTPUT_PATH\""
hexdump -v -e '1/8 "%u," 1/8 "%u," 1/8 "%u," 1/8 "%u\n"' "$RAW_PROFILE_DATA_OUTPUT_PATH" >> "$PROFILE_DATA_OUTPUT_PATH"

echo "Profile data saved to $PROFILE_DATA_OUTPUT_PATH"

echo "rm $SRC_DIR/profiler.o $SRC_DIR/profiler"
rm $SRC_DIR/profiler.o $SRC_DIR/profiler
