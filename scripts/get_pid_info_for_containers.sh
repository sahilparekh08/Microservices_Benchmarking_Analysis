#!/bin/bash

printf "%-15s %-40s %-15s %-20s %-20s\n" "CONTAINER_ID" "CONTAINER_NAME" "STATUS" "FIRST_PID_AFFINITY" "PIDS"

docker ps -q | while read cid; do
    cname=$(docker inspect --format "{{.Name}}" "$cid" | sed 's|/||')
    status=$(docker inspect --format "{{.State.Status}}" "$cid")
    pids=$(docker top "$cid" -eo pid | awk 'NR>1' | paste -sd ",")
    first_pid=$(echo "$pids" | cut -d',' -f1)

    if [[ -n "$first_pid" ]]; then
        affinity=$(taskset -pc "$first_pid" 2>/dev/null | awk -F': ' '{print $2}')
        affinity_numeric=$(echo "$affinity" | tr ',' '\n' | sort -n | paste -sd ",")
    else
        affinity="N/A"
        affinity_numeric="9999"
    fi

    printf "%-15s %-40s %-15s %-20s %-20s\n" "$cid" "$cname" "$status" "$affinity_numeric" "$pids"
done | sort -k4,4n
