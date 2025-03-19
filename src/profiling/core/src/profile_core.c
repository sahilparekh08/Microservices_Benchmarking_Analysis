#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sched.h>
#include <time.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <string.h>
#include <signal.h>
#include "profile_core.h"
#include "msr_constants.h"

// Linux-specific memory mapping flags
#ifndef MAP_POPULATE
#define MAP_POPULATE 0x1000
#endif
#ifndef MADV_SEQUENTIAL
#define MADV_SEQUENTIAL 2
#endif

// Linux-specific CPU set type
#ifndef CPU_SET_T_DEFINED
typedef unsigned long cpu_set_t;
#define CPU_SET_T_DEFINED
#endif

// MSR definitions for Haswell/Broadwell (E5 v3) architecture
#define IA32_PERF_GLOBAL_CTRL 0x38F
#define IA32_PERFEVTSEL0      0x186
#define IA32_PERFEVTSEL1      0x187
#define IA32_PERFEVTSEL2      0x188
#define IA32_PMC0             0xC1
#define IA32_PMC1             0xC2
#define IA32_PMC2             0xC3

// Event codes for E5 v3 (Haswell/Broadwell)
#define LLC_LOADS_EVENT       0x2E    // Event 0x2E, Umask 0x4F
#define LLC_LOADS_UMASK       0x4F
#define LLC_MISSES_EVENT      0x2E    // Event 0x2E, Umask 0x41
#define LLC_MISSES_UMASK      0x41
#define INSTR_RETIRED_EVENT   0xC0    // Event 0xC0, Umask 0x00
#define INSTR_RETIRED_UMASK   0x00

// Buffer size settings
#define BUFFER_SIZE 50000000 // Allow up to 50 million samples in memory

// Uncomment to print performance statistics every second
// #define PRINT_STATS_EVERY_SECOND 1

// Global variables
static sample_t *mapped_file;
static uint64_t total_samples = 0;
static size_t file_size;
static int output_file_fd = -1;
static volatile int should_exit = 0;

// MSR access helper functions - optimized inline versions
static inline int open_msr(int core) {
    char msr_path[64];
    snprintf(msr_path, sizeof(msr_path), "/dev/cpu/%d/msr", core);
    return open(msr_path, O_RDWR);
}

static inline uint64_t read_msr(int fd, uint32_t reg) {
    uint64_t value;
    pread(fd, &value, sizeof(value), reg);
    return value;
}

static inline void write_msr(int fd, uint32_t reg, uint64_t value) {
    pwrite(fd, &value, sizeof(value), reg);
}

// Setup PMU counters
int setup_pmu(int msr_fd) {
    // Disable all counters first
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0);
    
    // Configure LLC_LOADS counter
    write_msr(msr_fd, IA32_PERFEVTSEL0, 
              (LLC_LOADS_EVENT | (LLC_LOADS_UMASK << 8) | (1ULL << 16) | (1ULL << 22)));
    
    // Configure LLC_MISSES counter
    write_msr(msr_fd, IA32_PERFEVTSEL1, 
              (LLC_MISSES_EVENT | (LLC_MISSES_UMASK << 8) | (1ULL << 16) | (1ULL << 22)));
    
    // Configure INSTRUCTIONS_RETIRED counter
    write_msr(msr_fd, IA32_PERFEVTSEL2, 
              (INSTR_RETIRED_EVENT | (INSTR_RETIRED_UMASK << 8) | (1ULL << 16) | (1ULL << 22)));
    
    // Reset counter values
    write_msr(msr_fd, IA32_PMC0, 0);
    write_msr(msr_fd, IA32_PMC1, 0);
    write_msr(msr_fd, IA32_PMC2, 0);
    
    // Enable the configured counters (bits 0, 1, and 2)
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0x7);
    
    return 0;
}

// Open output file and prepare for memory mapping
int open_output_file(const char *filename, uint64_t max_samples) {
    output_file_fd = open(filename, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (output_file_fd == -1) {
        perror("Error opening output file");
        return -1;
    }
    
    // Set file size
    file_size = sizeof(sample_t) * max_samples;
    if (ftruncate(output_file_fd, file_size) == -1) {
        perror("Error setting file size");
        close(output_file_fd);
        return -1;
    }
    
    // Map the file into memory with MAP_POPULATE for better performance
    mapped_file = mmap(NULL, file_size, PROT_WRITE, MAP_SHARED | MAP_POPULATE, output_file_fd, 0);
    if (mapped_file == MAP_FAILED) {
        perror("Error mapping file");
        close(output_file_fd);
        return -1;
    }
    
    // Advise kernel about our access pattern
    madvise(mapped_file, file_size, MADV_SEQUENTIAL);
    
    return 0;
}

// Finalize output file
void close_output_file(void) {
    if (mapped_file != MAP_FAILED && mapped_file != NULL) {
        // Resize file to match actual samples
        if (ftruncate(output_file_fd, sizeof(sample_t) * total_samples) == -1) {
            perror("Warning: Error resizing output file");
        }
        
        // Unmap memory
        if (munmap(mapped_file, file_size) == -1) {
            perror("Warning: Error unmapping file");
        }
        mapped_file = NULL;
    }
    
    if (output_file_fd != -1) {
        close(output_file_fd);
        output_file_fd = -1;
    }
}

// Signal handler
void signal_handler(int signum) {
    printf("\nReceived signal %d. Will exit after current batch.\n", signum);
    should_exit = 1;
}

int main(int argc, char *argv[]) {
    if (argc != 5) {
        printf("Usage: %s <core_to_pin> <target_core> <duration_seconds> <data_file_path>\n", argv[0]);
        return EXIT_FAILURE;
    }
    
    int core_to_pin = atoi(argv[1]);
    int target_core = atoi(argv[2]);
    int duration_sec = atoi(argv[3]);
    const char* bin_file_path = argv[4];
    
    printf("Ultra-High-Performance Profiler started. PID: %d\n", getpid());
    printf("Settings: pinned to core [%d], profiling core [%d], for duration [%d sec]\n", 
           core_to_pin, target_core, duration_sec);
    
    // Set up signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Set maximum real-time priority
    struct sched_param param;
    param.sched_priority = sched_get_priority_max(SCHED_FIFO);
    if (sched_setscheduler(0, SCHED_FIFO, &param) == -1) {
        perror("Warning: Could not set real-time priority");
    }
    
    // Pin to specified core
    cpu_set_t cpu_set;
    CPU_ZERO(&cpu_set);
    CPU_SET(core_to_pin, &cpu_set);
    if (sched_setaffinity(0, sizeof(cpu_set), &cpu_set) == -1) {
        perror("Error setting CPU affinity");
        return EXIT_FAILURE;
    }
    
    // Lock all memory
    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("Warning: mlockall failed");
    }
    
    // Open MSR device
    int msr_fd = open_msr(target_core);
    if (msr_fd < 0) {
        perror("Error opening MSR device. Try running with sudo");
        return EXIT_FAILURE;
    }
    
    // Open and map output file
    open_output_file(bin_file_path, BUFFER_SIZE);
    
    // Setup PMU counters
    setup_pmu(msr_fd);
    
    // Calculate end time
    struct timespec ts_mono, ts_real;
    clock_gettime(CLOCK_MONOTONIC, &ts_mono);
    uint64_t start_time = (uint64_t)ts_mono.tv_sec * 1000000000ULL + ts_mono.tv_nsec;
    uint64_t end_time = start_time + (duration_sec * 1000000000ULL);

    #ifdef PRINT_STATS_EVERY_SECOND
    uint64_t next_status_time = start_time + 1000000000ULL;
    uint64_t last_samples = 0;
    #endif
    
    // Variables for counter values
    uint64_t prev_llc_loads = read_msr(msr_fd, IA32_PMC0);
    uint64_t prev_llc_misses = read_msr(msr_fd, IA32_PMC1);
    uint64_t prev_instr_retired = read_msr(msr_fd, IA32_PMC2);
    uint64_t curr_llc_loads, curr_llc_misses, curr_instr_retired;
    
    printf("Collection started at %lu, will run for %d seconds\n", start_time, duration_sec);
    
    // Main profiling loop - optimized for maximum speed
    while (!should_exit) {
        // Get current timestamps (both monotonic and real time)
        clock_gettime(CLOCK_MONOTONIC, &ts_mono);
        clock_gettime(CLOCK_REALTIME, &ts_real);
        
        uint64_t now_mono = (uint64_t)ts_mono.tv_sec * 1000000000ULL + ts_mono.tv_nsec;
        uint64_t now_real = (uint64_t)ts_real.tv_sec * 1000000000ULL + ts_real.tv_nsec;
        
        if (now_mono >= end_time) {
            break;
        }
        
#ifdef PRINT_STATS_EVERY_SECOND
        // Performance status update every second
        if (now_mono >= next_status_time) {
            uint64_t samples_this_second = total_samples - last_samples;
            printf("Rate: %lu samples/sec (total: %lu)\n", samples_this_second, total_samples);
            next_status_time += 1000000000ULL;
            last_samples = total_samples;
        }
#endif
        
        // Read counter values - done in one tight block to minimize time between reads
        curr_llc_loads = read_msr(msr_fd, IA32_PMC0);
        curr_llc_misses = read_msr(msr_fd, IA32_PMC1);
        curr_instr_retired = read_msr(msr_fd, IA32_PMC2);
        
        // Store both monotonic and real time
        mapped_file[total_samples].monotonic_time = now_mono;
        mapped_file[total_samples].real_time = now_real;
        
        // Store counter deltas directly
        mapped_file[total_samples].llc_loads = curr_llc_loads - prev_llc_loads;
        mapped_file[total_samples].llc_misses = curr_llc_misses - prev_llc_misses;
        mapped_file[total_samples].instr_retired = curr_instr_retired - prev_instr_retired;
        
        // Update previous values
        prev_llc_loads = curr_llc_loads;
        prev_llc_misses = curr_llc_misses;
        prev_instr_retired = curr_instr_retired;
        
        // Increment sample counter
        total_samples++;
        
        // Check for buffer overflow
        if (total_samples >= BUFFER_SIZE) {
            printf("Buffer full at %lu samples, stopping\n", total_samples);
            break;
        }
        
        // No sleep or pause - run at absolute maximum speed
    }
    
    // Disable counters
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0);
    close(msr_fd);
    
    // Print statistics
    struct timespec end_ts;
    clock_gettime(CLOCK_MONOTONIC, &end_ts);
    uint64_t actual_end_time = (uint64_t)end_ts.tv_sec * 1000000000ULL + end_ts.tv_nsec;
    double elapsed_seconds = (actual_end_time - start_time) / 1000000000.0;
    
    printf("\nProfiling complete:\n");
    printf("- Total samples: %lu\n", total_samples);
    printf("- Elapsed time: %.2f seconds\n", elapsed_seconds);
    printf("- Average sampling rate: %.2f samples/second\n", total_samples / elapsed_seconds);
    printf("- Data saved to: %s\n", bin_file_path);
    
    // Clean up
    close_output_file();
    
    return 0;
}