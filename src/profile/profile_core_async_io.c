// ALMOST SAME PERFORMANCE AS WITHOUT AIO

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
#include <aio.h>
#include <pthread.h>
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
#define BATCH_SIZE 100
#define BUFFER_SIZE 1000000  // Number of samples to keep in memory before flushing to disk
#define WAIT_TIME_BETWEEN_SAMPLES_IN_NS 10000  // Time to wait between samples in nanoseconds

// Global variables
sample_t *samples;
volatile int running = 1;
pthread_mutex_t buffer_mutex = PTHREAD_MUTEX_INITIALIZER;
int output_fd = -1;
int sample_index = 0;
uint64_t total_samples = 0;
int target_core = 0;
int duration_sec = 0;

// AIO control blocks for non-blocking I/O
struct aiocb aio_control;
int aio_in_progress = 0;

// Get file descriptor for MSR access
int open_msr(int core) {
    char msr_path[64];
    snprintf(msr_path, sizeof(msr_path), "/dev/cpu/%d/msr", core);
    return open(msr_path, O_RDWR);
}

// Efficient MSR read function
uint64_t read_msr(int fd, uint32_t reg) {
    uint64_t value;
    if (pread(fd, &value, sizeof(value), reg) != sizeof(value)) {
        perror("Error reading MSR");
        running = 0;  // Signal to stop on error
        return 0;
    }
    return value;
}

// Write MSR value
void write_msr(int fd, uint32_t reg, uint64_t value) {
    if (pwrite(fd, &value, sizeof(value), reg) != sizeof(value)) {
        perror("Error writing MSR");
        running = 0;  // Signal to stop on error
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

// Initialize non-blocking I/O
int init_aio(const char *filename) {
    // Open the file with O_NONBLOCK for non-blocking operations
    output_fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC | O_NONBLOCK, 0644);
    if (output_fd < 0) {
        perror("Error opening output file");
        return -1;
    }
    
    // Initialize the AIO control block
    memset(&aio_control, 0, sizeof(struct aiocb));
    aio_control.aio_fildes = output_fd;
    
    return 0;
}

// Wait for any in-progress AIO to complete
void wait_for_aio() {
    if (aio_in_progress) {
        const struct aiocb *cblist[1];
        cblist[0] = &aio_control;
        aio_suspend(cblist, 1, NULL);
        
        if (aio_error(&aio_control) != 0) {
            perror("AIO error");
            exit(EXIT_FAILURE);
        }
        
        ssize_t ret = aio_return(&aio_control);
        if (ret != aio_control.aio_nbytes) {
            fprintf(stderr, "AIO incomplete write: %zd of %zu bytes written\n", 
                    ret, aio_control.aio_nbytes);
            exit(EXIT_FAILURE);
        }
        
        aio_in_progress = 0;
    }
}

// Flush the current buffer to disk using AIO
void flush_buffer_to_disk() {
    if (sample_index == 0) return;  // Nothing to flush
    
    // Wait for any existing AIO operation to complete
    wait_for_aio();
    
    // Set up the AIO operation
    aio_control.aio_buf = samples;
    aio_control.aio_nbytes = sizeof(sample_t) * sample_index;
    aio_control.aio_offset = (off_t)total_samples * sizeof(sample_t);
    
    // Submit the AIO request
    if (aio_write(&aio_control) < 0) {
        perror("Error submitting AIO write");
        exit(EXIT_FAILURE);
    }
    aio_in_progress = 1;
    
    // Reset the buffer index
    sample_index = 0;
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

// Signal handler for graceful termination
void signal_handler(int signum) {
    printf("\nReceived signal %d. Cleaning up and exiting...\n", signum);
    running = 0;
}

// Sampling thread function
void* sampling_thread(void *arg) {
    // Set lowest priority to minimize impact on target program
    if (setpriority(PRIO_PROCESS, 0, 19) != 0) {
        perror("Warning: Failed to set nice value");
    }
    
    // Pin to the target core
    cpu_set_t cpu_set;
    CPU_ZERO(&cpu_set);
    CPU_SET(target_core, &cpu_set);
    if (pthread_setaffinity_np(pthread_self(), sizeof(cpu_set), &cpu_set) != 0) {
        perror("Error setting CPU affinity");
        running = 0;
        return NULL;
    }
    
    // Lock memory to prevent paging
    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("Warning: mlockall failed");
    }
    
    // Open MSR device
    int msr_fd = open_msr(target_core);
    if (msr_fd < 0) {
        fprintf(stderr, "Error opening MSR device. Try running with sudo\n");
        running = 0;
        return NULL;
    }
    
    // Setup performance counters
    setup_pmu(msr_fd);
    
    // Sampling variables
    uint64_t prev_llc_loads = 0, prev_llc_misses = 0, prev_instr_retired = 0;
    uint64_t curr_llc_loads, curr_llc_misses, curr_instr_retired;
    uint64_t start_time = get_monotonic_ns();
    uint64_t end_time = start_time + (duration_sec * 1000000000ULL);
    uint64_t next_sample_time = start_time + WAIT_TIME_BETWEEN_SAMPLES_IN_NS;
    
    // Batch processing variables
    sample_t batch_samples[BATCH_SIZE];
    int batch_index = 0;
    
    printf("Starting profiling on core %d for %d seconds...\n", target_core, duration_sec);
    
    // Main sampling loop
    while (running && get_monotonic_ns() < end_time) {
        uint64_t now = get_monotonic_ns();
        
        // Check if it's time for the next sample
        if (now >= next_sample_time) {
            // Read counter values 
            curr_llc_loads = read_msr(msr_fd, IA32_PMC0);
            curr_llc_misses = read_msr(msr_fd, IA32_PMC1);
            curr_instr_retired = read_msr(msr_fd, IA32_PMC2);
            
            // Store in batch buffer - include both real time and monotonic time
            batch_samples[batch_index].monotonic_time = now;
            get_real_time(&batch_samples[batch_index].real_time);
            batch_samples[batch_index].llc_loads = curr_llc_loads - prev_llc_loads;
            batch_samples[batch_index].llc_misses = curr_llc_misses - prev_llc_misses;
            batch_samples[batch_index].instr_retired = curr_instr_retired - prev_instr_retired;
            
            // Update previous values
            prev_llc_loads = curr_llc_loads;
            prev_llc_misses = curr_llc_misses;
            prev_instr_retired = curr_instr_retired;
            
            batch_index++;
            next_sample_time += WAIT_TIME_BETWEEN_SAMPLES_IN_NS;
            
            // If we're more than 50% behind schedule, catch up
            if (now > next_sample_time) {
                next_sample_time = now + WAIT_TIME_BETWEEN_SAMPLES_IN_NS;
            }
            
            // Process batch when full
            if (batch_index == BATCH_SIZE) {
                // Lock the mutex before accessing the shared buffer
                pthread_mutex_lock(&buffer_mutex);
                
                // Copy batch to main buffer
                memcpy(&samples[sample_index], batch_samples, sizeof(sample_t) * batch_index);
                sample_index += batch_index;
                total_samples += batch_index;
                
                // Check if we need to flush the buffer to disk
                if (sample_index >= BUFFER_SIZE) {
                    flush_buffer_to_disk();
                }
                
                pthread_mutex_unlock(&buffer_mutex);
                batch_index = 0;
                
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
        pthread_mutex_lock(&buffer_mutex);
        memcpy(&samples[sample_index], batch_samples, sizeof(sample_t) * batch_index);
        sample_index += batch_index;
        total_samples += batch_index;
        pthread_mutex_unlock(&buffer_mutex);
        flush_buffer_to_disk();
    }
    
    // Disable counters
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0);
    close(msr_fd);
    
    return NULL;
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "Usage: %s <target_core> <duration_seconds> <data_file_path>\n", argv[0]);
        return EXIT_FAILURE;
    }
    
    target_core = atoi(argv[1]);
    duration_sec = atoi(argv[2]);
    const char* bin_file_path = argv[3];
    
    // Set up signal handlers for graceful termination
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Allocate memory for in-memory buffer
    samples = malloc(sizeof(sample_t) * BUFFER_SIZE);
    if (!samples) {
        perror("Failed to allocate buffer");
        return EXIT_FAILURE;
    }
    
    // Initialize AIO for non-blocking file output
    if (init_aio(bin_file_path) != 0) {
        free(samples);
        return EXIT_FAILURE;
    }
    
    // Create sampling thread
    pthread_t sampler_thread;
    if (pthread_create(&sampler_thread, NULL, sampling_thread, NULL) != 0) {
        perror("Failed to create sampling thread");
        close(output_fd);
        free(samples);
        return EXIT_FAILURE;
    }
    
    // Main thread can do other work or just wait for the sampler to finish
    printf("Main thread waiting for sampler to complete...\n");
    
    // Wait for sampling thread to finish
    pthread_join(sampler_thread, NULL);
    
    // Make sure all data is flushed before exit
    pthread_mutex_lock(&buffer_mutex);
    if (sample_index > 0) {
        flush_buffer_to_disk();
    }
    pthread_mutex_unlock(&buffer_mutex);
    
    // Wait for any pending AIO operations to complete
    wait_for_aio();
    
    // Close output file
    if (output_fd >= 0) {
        close(output_fd);
    }
    
    printf("Profiling completed. Collected %lu samples.\n", total_samples);
    printf("Data saved to %s\n", bin_file_path);
    
    // Free resources
    free(samples);
    
    return 0;
}
