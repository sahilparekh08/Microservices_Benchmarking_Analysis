#define _GNU_SOURCE
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
#include <sys/resource.h>
#include <string.h>
#include <signal.h>
#include "profile_core.h"

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
#define BATCH_SIZE 1000
#define BUFFER_SIZE 1000000 // Number of samples to keep in memory before flushing to disk
#define WAIT_TIME_BETWEEN_SAMPLES_IN_NS 10000  // Time to wait between samples in nanoseconds

// Global variables
sample_t *samples;
int sample_index = 0;
uint64_t total_samples = 0;
int output_file_fd = -1;

// MSR access helper functions
int open_msr(int core) {
    char msr_path[64];
    snprintf(msr_path, sizeof(msr_path), "/dev/cpu/%d/msr", core);
    return open(msr_path, O_RDWR);
}

uint64_t read_msr(int fd, uint32_t reg) {
    uint64_t value;
    if (pread(fd, &value, sizeof(value), reg) != sizeof(value)) {
        perror("Error reading MSR");
        exit(EXIT_FAILURE);
    }
    return value;
}

void write_msr(int fd, uint32_t reg, uint64_t value) {
    if (pwrite(fd, &value, sizeof(value), reg) != sizeof(value)) {
        perror("Error writing MSR");
        exit(EXIT_FAILURE);
    }
}

// Flush the current buffer to disk
void flush_buffer_to_disk() {
    if (sample_index == 0) return;  // Nothing to flush

    if(write(output_file_fd, samples, sizeof(sample_t) * sample_index) != sizeof(sample_t) * sample_index) {
        perror("Error writing to output file");
        exit(EXIT_FAILURE);
    }
    
    // Reset the buffer index
    sample_index = 0;
    
    // Flush to ensure data is written
    if (fsync(output_file_fd) == -1) {
        perror("Error flushing output file");
        exit(EXIT_FAILURE);
    }
}

// Setup PMU counters
void setup_pmu(int msr_fd) {
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
}

// Get current timestamp in nanoseconds (monotonic clock for precise intervals)
uint64_t get_monotonic_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

// Get real timestamp (for correlation with other system events)
void get_real_time(struct timespec *ts) {
    clock_gettime(CLOCK_REALTIME, ts);
}

// Open output file and prepare for streaming
void open_output_file(const char *filename) {
    output_file_fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (output_file_fd == -1) {
        perror("Error opening output file");
        exit(EXIT_FAILURE);
    }
}

// Close output file and finalize
void close_output_file() {
    if(output_file_fd != -1) {
        flush_buffer_to_disk();
        close(output_file_fd);
    }
    output_file_fd = -1;
}

// Signal handler for graceful termination
void signal_handler(int signum) {
    printf("\nReceived signal %d. Cleaning up and exiting...\n", signum);
    close_output_file();
    free(samples);
    exit(0);
}

int main(int argc, char *argv[]) {
    printf("Profiler started. PID: %d\n", getpid());

    if (argc != 5) {
        printf("Usage: %s <core_to_pin> <target_core> <duration_seconds> <data_file_path>\n", argv[0]);
        return EXIT_FAILURE;
    }
    
    int core_to_pin = atoi(argv[1]);
    int target_core = atoi(argv[2]);
    int duration_sec = atoi(argv[3]);
    const char* bin_file_path = argv[4];

    printf("Profiler started with core_to_pin: %d, target_core: %d, duration_sec: %d\n", core_to_pin, target_core, duration_sec);
    
    // Set up signal handlers for graceful termination
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Set lowest priority to minimize impact on target program
    if (setpriority(PRIO_PROCESS, 0, 19) != 0) {
        perror("Warning: Failed to set nice value");
    }
    printf("Process priority set to nice value 19 (lowest priority).\n");
    
    // Allocate memory for in-memory buffer
    samples = malloc(sizeof(sample_t) * BUFFER_SIZE);
    if (!samples) {
        perror("Failed to allocate buffer");
        return EXIT_FAILURE;
    }
    printf("Buffer allocated with size %lu bytes.\n", sizeof(sample_t) * BUFFER_SIZE);
    
    // Open output file for streaming
    open_output_file(bin_file_path);
    printf("Output file opened: %s\n", bin_file_path);
    
    // Pin to the target core
    cpu_set_t cpu_set;
    CPU_ZERO(&cpu_set);
    CPU_SET(core_to_pin, &cpu_set);
    if (sched_setaffinity(0, sizeof(cpu_set), &cpu_set) == -1) {
        perror("Error setting CPU affinity");
        free(samples);
        close_output_file();
        return EXIT_FAILURE;
    }
    printf("Pinned profiler to core %d\n", core_to_pin);
    
    // Lock memory to prevent paging
    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("Warning: mlockall failed");
    }
    printf("Memory locked to prevent paging.\n");
    
    // Open MSR device
    int msr_fd = open_msr(target_core);
    if (msr_fd < 0) {
        perror("Error opening MSR device. Try running with sudo");
        free(samples);
        close_output_file();
        return EXIT_FAILURE;
    }
    printf("MSR device opened for core %d\n", target_core);
    
    // Setup performance counters
    setup_pmu(msr_fd);
    printf("Performance counters set up.\n");
    
    // Sampling variables
    uint64_t prev_llc_loads = 0, prev_llc_misses = 0, prev_instr_retired = 0;
    uint64_t curr_llc_loads, curr_llc_misses, curr_instr_retired;
    uint64_t start_time = get_monotonic_ns();
    uint64_t end_time = start_time + (duration_sec * 1000000000ULL);
    uint64_t next_sample_time = start_time + WAIT_TIME_BETWEEN_SAMPLES_IN_NS;
    
    // Batch processing variables
    sample_t batch_samples[BATCH_SIZE];
    int batch_index = 0;
    
    printf("Running on core [%d] and profiling core [%d] for [%d] seconds...\n", core_to_pin, target_core, duration_sec);
    
    // Main sampling loop
    while (get_monotonic_ns() < end_time) {
        uint64_t now = get_monotonic_ns();
        
        // Check if it's time for the next sample
        if (now >= next_sample_time) {
            // Read counter values
            curr_llc_loads = read_msr(msr_fd, IA32_PMC0);
            curr_llc_misses = read_msr(msr_fd, IA32_PMC1);
            curr_instr_retired = read_msr(msr_fd, IA32_PMC2);
            
            // Store in batch buffer - include both real time and monotonic time
            get_real_time(&batch_samples[batch_index].real_time);
            batch_samples[batch_index].monotonic_time = now;
            batch_samples[batch_index].llc_loads = curr_llc_loads - prev_llc_loads;
            batch_samples[batch_index].llc_misses = curr_llc_misses - prev_llc_misses;
            batch_samples[batch_index].instr_retired = curr_instr_retired - prev_instr_retired;
            
            // Update previous values
            prev_llc_loads = curr_llc_loads;
            prev_llc_misses = curr_llc_misses;
            prev_instr_retired = curr_instr_retired;
            
            batch_index++;
            next_sample_time += WAIT_TIME_BETWEEN_SAMPLES_IN_NS;  // Next 10 microseconds

            // Check if we need to adjust the next sample time
            if (now > next_sample_time) {
                next_sample_time = now + WAIT_TIME_BETWEEN_SAMPLES_IN_NS;
            }
            
            // Process batch when full
            if (batch_index == BATCH_SIZE) {
                // Copy batch to main buffer
                memcpy(&samples[sample_index], batch_samples, sizeof(sample_t) * batch_index);
                sample_index += batch_index;
                total_samples += batch_index;
                batch_index = 0;
                
                // Check if we need to flush the buffer to disk
                if (sample_index >= BUFFER_SIZE) {
                    flush_buffer_to_disk();
                }
                
                // Yield to target program
                sched_yield();
            }
        }
        
        // Very short pause to avoid burning CPU unnecessarily
        for (int i = 0; i < 5; i++) {
            __asm__ volatile("pause");
        }
    }
    
    // Process any remaining samples in the batch
    if (batch_index > 0) {
        memcpy(&samples[sample_index], batch_samples, sizeof(sample_t) * batch_index);
        total_samples += batch_index;
        flush_buffer_to_disk();
    }
    
    // Clean up
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0);  // Disable counters
    close(msr_fd);
    
    // Close output file
    close_output_file();
    
    printf("Profiling completed. Collected %lu samples.\n", total_samples);
    printf("Data saved to %s\n", bin_file_path);
    
    // Free resources
    free(samples);
    
    return 0;
}