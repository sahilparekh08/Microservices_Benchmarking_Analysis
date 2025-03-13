#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include <sys/ioctl.h>
#include <linux/perf_event.h>
#include <asm/unistd.h>
#include <sched.h>
#include <errno.h>

#define SAMPLE_INTERVAL_MICROS 10

int perf_event_open(struct perf_event_attr *hw_event, pid_t pid, int cpu, int group_fd, unsigned long flags) {
    return syscall(__NR_perf_event_open, hw_event, pid, cpu, group_fd, flags);
}

void pin_to_core(int core) {
    cpu_set_t mask;
    CPU_ZERO(&mask);
    CPU_SET(core, &mask);
    if (sched_setaffinity(0, sizeof(mask), &mask) != 0) {
        perror("sched_setaffinity");
        exit(EXIT_FAILURE);
    }
}

uint64_t read_counter(int fd) {
    uint64_t value;
    if (read(fd, &value, sizeof(value)) == -1) {
        perror("read");
        exit(EXIT_FAILURE);
    }
    return value;
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "Usage: %s <core> <run_seconds> <output_file>\n", argv[0]);
        return EXIT_FAILURE;
    }

    int core = atoi(argv[1]);
    int run_seconds = atoi(argv[2]);
    char *output_file = argv[3];

    pin_to_core(core);
    printf("Pinned to core %d\n", core);

    struct perf_event_attr pe = {0};
    pe.type = PERF_TYPE_HW_CACHE;
    pe.size = sizeof(struct perf_event_attr);
    pe.disabled = 1;
    pe.exclude_kernel = 1;
    pe.exclude_hv = 1;

    pe.config = (PERF_COUNT_HW_CACHE_LL | (PERF_COUNT_HW_CACHE_OP_READ << 8) | (PERF_COUNT_HW_CACHE_RESULT_ACCESS << 16));
    int fd_llc_loads = perf_event_open(&pe, 0, core, -1, 0);
    if (fd_llc_loads == -1) {
        perror("perf_event_open (LLC Loads)");
        return EXIT_FAILURE;
    }

    pe.config = (PERF_COUNT_HW_CACHE_LL | (PERF_COUNT_HW_CACHE_OP_READ << 8) | (PERF_COUNT_HW_CACHE_RESULT_MISS << 16));
    int fd_llc_misses = perf_event_open(&pe, 0, core, -1, 0);
    if (fd_llc_misses == -1) {
        perror("perf_event_open (LLC Misses)");
        return EXIT_FAILURE;
    }

    pe.type = PERF_TYPE_HARDWARE;
    pe.config = PERF_COUNT_HW_INSTRUCTIONS;
    int fd_instructions = perf_event_open(&pe, 0, core, -1, 0);
    if (fd_instructions == -1) {
        perror("perf_event_open (Instructions Retired)");
        return EXIT_FAILURE;
    }

    FILE *fp = fopen(output_file, "w");
    if (!fp) {
        perror("fopen");
        return EXIT_FAILURE;
    }
    printf("Output file: %s\n", output_file);
    fprintf(fp, "Time,LLC-loads,LLC-misses,Instructions\n");

    ioctl(fd_llc_loads, PERF_EVENT_IOC_ENABLE, 0);
    ioctl(fd_llc_misses, PERF_EVENT_IOC_ENABLE, 0);
    ioctl(fd_instructions, PERF_EVENT_IOC_ENABLE, 0);

    struct timespec start_time, current_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);
    uint64_t llc_loads_prev = 0, llc_misses_prev = 0, instructions_prev = 0;

    printf("Profiling for %d seconds\n", run_seconds);

    struct timespec real_start_time;
    clock_gettime(CLOCK_REALTIME, &real_start_time);
    printf("Profiling started at %ld.%09ld\n", real_start_time.tv_sec, real_start_time.tv_nsec);

    while (1) {
        struct timespec real_time;
        clock_gettime(CLOCK_REALTIME, &real_time);
        clock_gettime(CLOCK_MONOTONIC, &current_time);

        double elapsed_time = (current_time.tv_sec - start_time.tv_sec) + 
                            (current_time.tv_nsec - start_time.tv_nsec) / 1e9;
        if (elapsed_time >= run_seconds) break;

        uint64_t llc_loads_curr = read_counter(fd_llc_loads);
        uint64_t llc_misses_curr = read_counter(fd_llc_misses);
        uint64_t instructions_curr = read_counter(fd_instructions);

        uint64_t llc_loads = llc_loads_curr - llc_loads_prev;
        uint64_t llc_misses = llc_misses_curr - llc_misses_prev;
        uint64_t instructions = instructions_curr - instructions_prev;

        fprintf(fp, "%ld%ld,%lu,%lu,%lu\n", real_time.tv_sec, real_time.tv_nsec / 1000, llc_loads, llc_misses, instructions);
        fflush(fp);

        usleep(SAMPLE_INTERVAL_MICROS);

        llc_loads_prev = llc_loads_curr;
        llc_misses_prev = llc_misses_curr;
        instructions_prev = instructions_curr;
    }
    
    struct timespec real_end_time;
    clock_gettime(CLOCK_REALTIME, &real_end_time);
    printf("Profiling ended at %ld.%09ld\n", real_end_time.tv_sec, real_end_time.tv_nsec);

    ioctl(fd_llc_loads, PERF_EVENT_IOC_DISABLE, 0);
    ioctl(fd_llc_misses, PERF_EVENT_IOC_DISABLE, 0);
    ioctl(fd_instructions, PERF_EVENT_IOC_DISABLE, 0);

    fclose(fp);
    close(fd_llc_loads);
    close(fd_llc_misses);
    close(fd_instructions);

    return EXIT_SUCCESS;
}
