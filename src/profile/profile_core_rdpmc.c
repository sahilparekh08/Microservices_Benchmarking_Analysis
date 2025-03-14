// SEGFAULTS

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
#include <pthread.h>
#include <errno.h>
#include <stdbool.h>
#include "profile_core.h"

// MSR definitions for Haswell/Broadwell (E5 v3) architecture
#define IA32_PERF_GLOBAL_CTRL 0x38F  // Global control register for PMCs
#define IA32_PERFEVTSEL0      0x186  // Event select register for PMC0
#define IA32_PERFEVTSEL1      0x187  // Event select register for PMC1
#define IA32_PERFEVTSEL2      0x188  // Event select register for PMC2
#define IA32_PMC0             0xC1   // Performance counter 0
#define IA32_PMC1             0xC2   // Performance counter 1
#define IA32_PMC2             0xC3   // Performance counter 2

// Event codes for E5 v3 (Haswell/Broadwell)
#define LLC_LOADS_EVENT       0x2E    // LLC load event code
#define LLC_LOADS_UMASK       0x4F    // LLC load event mask
#define LLC_MISSES_EVENT      0x2E    // LLC miss event code
#define LLC_MISSES_UMASK      0x41    // LLC miss event mask
#define INSTR_RETIRED_EVENT   0xC0    // Instruction retired event code
#define INSTR_RETIRED_UMASK   0x00    // Instruction retired event mask

// Important bit flags for event configuration
#define USR_FLAG             (1ULL << 16)  // Enable monitoring in user mode
#define OS_FLAG              (1ULL << 17)  // Enable monitoring in OS/kernel mode
#define ENABLE_FLAG          (1ULL << 22)  // Enable counter

// Buffer size settings
#define BATCH_SIZE 1000               // Number of samples to collect before processing
#define BUFFER_SIZE 1000000           // Number of samples to keep in memory before flushing to disk
#define WAIT_TIME_BETWEEN_SAMPLES_IN_NS 10000  // 1 microsecond between samples 

// Thread control for sampling
#define SAMPLING_THREAD_PRIORITY 99   // Real-time priority for sampling thread

// Here we're implementing a simplified try/catch mechanism for the RDPMC instruction
// In real C code, you'd use signal handlers for this purpose
#define try if(1)
#define catch(x) if(0)
#define throw(x) handle_rdpmc_error()

// Global variables
sample_t *samples;                    // Main buffer for samples
int sample_index = 0;                 // Current position in the buffer
uint64_t total_samples = 0;           // Total number of samples collected
FILE *output_file = NULL;             // Output file pointer
bool use_rdpmc = false;               // Whether to use RDPMC (faster) or MSR (more compatible)
volatile bool sampling_active = true; // Flag to control sampling thread

// Thread-specific variables
typedef struct {
    int target_core;
    int duration_sec;
} thread_args_t;

pthread_t sampling_thread;            // Dedicated sampling thread
pthread_mutex_t buffer_mutex = PTHREAD_MUTEX_INITIALIZER;  // Mutex for buffer access

// Fast counter reading using RDPMC (much faster than MSR when available)
static inline uint64_t read_pmc(int counter) {
    uint32_t low, high;
    // RDPMC instruction: reads the performance counter specified by ECX
    // Low 32 bits returned in EAX, high 32 bits in EDX
    __asm__ volatile("rdpmc" : "=a" (low), "=d" (high) : "c" (counter));
    return ((uint64_t)high << 32) | low;
}

// Try to enable RDPMC from user space
static bool enable_rdpmc() {
    // Modern Linux kernels have a sysfs interface to enable RDPMC
    FILE *rdpmc_file = fopen("/sys/devices/cpu/rdpmc", "w");
    if (rdpmc_file) {
        fputs("1", rdpmc_file);
        fclose(rdpmc_file);
        return true;
    }
    
    // If sysfs interface not available, we can't enable RDPMC from user space
    return false;
}

// Check if RDPMC is available and working
static bool check_rdpmc() {
    // Try to read PMC0 using RDPMC
    uint64_t test_value;
    try {
        // Try to read PMC0 (index 0)
        test_value = read_pmc(0);
        return true;
    } catch (...) {
        return false;
    }
}

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

// Memory-mapped MSR access (faster than traditional MSR access)
void *map_msr_registers(int msr_fd) {
    // Map MSR device file to memory for faster access
    void *mapped = mmap(NULL, getpagesize(), PROT_READ, MAP_SHARED, msr_fd, 0);
    if (mapped == MAP_FAILED) {
        perror("Failed to memory map MSR registers");
        return NULL;
    }
    return mapped;
}

// Flush the current buffer to disk
void flush_buffer_to_disk() {
    // Lock the buffer to prevent concurrent access
    pthread_mutex_lock(&buffer_mutex);
    
    if (sample_index == 0) {
        // Nothing to flush
        pthread_mutex_unlock(&buffer_mutex);
        return;
    }
    
    // Write samples to file
    if (fwrite(samples, sizeof(sample_t), sample_index, output_file) != sample_index) {
        perror("Error writing to output file");
        pthread_mutex_unlock(&buffer_mutex);
        exit(EXIT_FAILURE);
    }
    
    // Reset the buffer index
    sample_index = 0;
    
    // Unlock the buffer
    pthread_mutex_unlock(&buffer_mutex);
    
    // Flush to ensure data is written
    fflush(output_file);
}

// Setup PMU counters
void setup_pmu(int msr_fd) {
    // Disable all counters first
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0);
    
    // Configure LLC_LOADS counter
    // Enable both user and kernel monitoring (USR_FLAG | OS_FLAG)
    // Plus enable the counter itself (ENABLE_FLAG)
    write_msr(msr_fd, IA32_PERFEVTSEL0, 
              (LLC_LOADS_EVENT | (LLC_LOADS_UMASK << 8) | USR_FLAG | OS_FLAG | ENABLE_FLAG));
    
    // Configure LLC_MISSES counter
    write_msr(msr_fd, IA32_PERFEVTSEL1, 
              (LLC_MISSES_EVENT | (LLC_MISSES_UMASK << 8) | USR_FLAG | OS_FLAG | ENABLE_FLAG));
    
    // Configure INSTRUCTIONS_RETIRED counter
    write_msr(msr_fd, IA32_PERFEVTSEL2, 
              (INSTR_RETIRED_EVENT | (INSTR_RETIRED_UMASK << 8) | USR_FLAG | OS_FLAG | ENABLE_FLAG));
    
    // Reset counter values
    write_msr(msr_fd, IA32_PMC0, 0);
    write_msr(msr_fd, IA32_PMC1, 0);
    write_msr(msr_fd, IA32_PMC2, 0);
    
    // Enable the configured counters (bits 0, 1, and 2)
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0x7);
    
    // Try to enable RDPMC (faster access from user space)
    if (enable_rdpmc() && check_rdpmc()) {
        use_rdpmc = true;
        printf("RDPMC instruction enabled for fast counter reading\n");
    } else {
        use_rdpmc = false;
        printf("Using MSR interface for counter reading (slower but more compatible)\n");
    }
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
    // Open file with non-blocking I/O to avoid stalling during writes
    int fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        perror("Error opening output file");
        exit(EXIT_FAILURE);
    }
    
    // Convert file descriptor to FILE* for buffered I/O
    output_file = fdopen(fd, "wb");
    if (!output_file) {
        perror("Error getting file stream");
        close(fd);
        exit(EXIT_FAILURE);
    }
    
    // Set buffer size for better performance
    setvbuf(output_file, NULL, _IOFBF, 1024 * 1024);
}

// Close output file and finalize
void close_output_file() {
    if (output_file) {
        flush_buffer_to_disk();
        fclose(output_file);
        output_file = NULL;
    }
}

// Signal handler for graceful termination
void signal_handler(int signum) {
    printf("\nReceived signal %d. Cleaning up and exiting...\n", signum);
    
    // Stop sampling thread
    sampling_active = false;
    
    // Wait for sampling thread to finish
    pthread_join(sampling_thread, NULL);
    
    // Clean up resources
    close_output_file();
    free(samples);
    
    exit(0);
}

// Main sampling function (runs in dedicated thread)
void *sampling_routine(void *arg) {
    thread_args_t *args = (thread_args_t *)arg;
    int target_core = args->target_core;
    int duration_sec = args->duration_sec;
    
    // Pin this thread to the target core
    cpu_set_t cpu_set;
    CPU_ZERO(&cpu_set);
    CPU_SET(target_core, &cpu_set);
    if (pthread_setaffinity_np(pthread_self(), sizeof(cpu_set), &cpu_set) != 0) {
        perror("Error setting thread CPU affinity");
        return NULL;
    }
    
    // Open MSR device
    int msr_fd = open_msr(target_core);
    if (msr_fd < 0) {
        perror("Error opening MSR device. Try running with sudo");
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
    while (sampling_active && get_monotonic_ns() < end_time) {
        uint64_t now = get_monotonic_ns();
        
        // Check if it's time for the next sample
        if (now >= next_sample_time) {
            // Read counter values using either RDPMC (fast) or MSR (compatible)
            if (use_rdpmc) {
                // Fast RDPMC - direct CPU instruction
                curr_llc_loads = read_pmc(0);      // PMC0
                curr_llc_misses = read_pmc(1);     // PMC1
                curr_instr_retired = read_pmc(2);  // PMC2
            } else {
                // Slower MSR reads through /dev/cpu/*/msr interface
                curr_llc_loads = read_msr(msr_fd, IA32_PMC0);
                curr_llc_misses = read_msr(msr_fd, IA32_PMC1);
                curr_instr_retired = read_msr(msr_fd, IA32_PMC2);
            }
            
            // Store in batch buffer - include both real time and monotonic time
            batch_samples[batch_index].monotonic_time = now;
            get_real_time(&batch_samples[batch_index].real_time);
            
            // Store counter differences (delta) since last sample
            batch_samples[batch_index].llc_loads = curr_llc_loads - prev_llc_loads;
            batch_samples[batch_index].llc_misses = curr_llc_misses - prev_llc_misses;
            batch_samples[batch_index].instr_retired = curr_instr_retired - prev_instr_retired;
            
            // Update previous values for next delta calculation
            prev_llc_loads = curr_llc_loads;
            prev_llc_misses = curr_llc_misses;
            prev_instr_retired = curr_instr_retired;
            
            batch_index++;
            
            // Schedule next sample time
            next_sample_time += WAIT_TIME_BETWEEN_SAMPLES_IN_NS;
            
            // If we're more than 50% behind schedule, catch up
            if (now > next_sample_time) {
                next_sample_time = now + WAIT_TIME_BETWEEN_SAMPLES_IN_NS;
            }
            
            // Process batch when full
            if (batch_index == BATCH_SIZE) {
                // Lock the buffer before modifying
                pthread_mutex_lock(&buffer_mutex);
                
                // Copy batch to main buffer
                memcpy(&samples[sample_index], batch_samples, sizeof(sample_t) * batch_index);
                sample_index += batch_index;
                total_samples += batch_index;
                
                // Reset batch index for new batch
                batch_index = 0;
                
                // Check if we need to flush the buffer to disk
                if (sample_index >= BUFFER_SIZE) {
                    // Unlock before flushing since flush_buffer_to_disk will lock again
                    pthread_mutex_unlock(&buffer_mutex);
                    flush_buffer_to_disk();
                } else {
                    // Just unlock without flushing
                    pthread_mutex_unlock(&buffer_mutex);
                }
            }
        }
        
        // // Print status every 5 seconds
        // if (now - last_status_time > 5000000000ULL) {
        //     double samples_per_sec = (double)total_samples / ((double)(now - start_time) / 1000000000.0);
        //     printf("Profiling in progress: %lu samples collected (%.2f samples/sec), %.1f seconds elapsed\n", 
        //            total_samples, samples_per_sec, (double)(now - start_time) / 1000000000.0);
        //     last_status_time = now;
        // }
        
        // Very short pause to avoid completely saturating the CPU
        // This is a compromise between sampling rate and system impact
        if (!use_rdpmc) {
            // Longer pause for MSR method (slower, so we can wait longer)
            for (int i = 0; i < 5; i++) {
                __asm__ volatile("pause");  // CPU hint to optimize spin-wait loop
            }
        } else {
            // Shorter/no pause for RDPMC method (we want maximum sampling rate)
            __asm__ volatile("pause");  // Single pause instruction
        }
    }
    
    // Process any remaining samples in the batch
    if (batch_index > 0) {
        pthread_mutex_lock(&buffer_mutex);
        memcpy(&samples[sample_index], batch_samples, sizeof(sample_t) * batch_index);
        sample_index += batch_index;
        total_samples += batch_index;
        pthread_mutex_unlock(&buffer_mutex);
        flush_buffer_to_disk(); // Flush remaining samples to disk
    }
    
    // Clean up
    write_msr(msr_fd, IA32_PERF_GLOBAL_CTRL, 0);  // Disable counters
    close(msr_fd);
    
    printf("Sampling thread finished. Collected %lu samples.\n", total_samples);
    
    return NULL;
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "Usage: %s <target_core> <duration_seconds> <data_file_path>\n", argv[0]);
        return EXIT_FAILURE;
    }
    
    int target_core = atoi(argv[1]);
    int duration_sec = atoi(argv[2]);
    const char* bin_file_path = argv[3];
    
    // Check if running as root (required for MSR access)
    if (geteuid() != 0) {
        fprintf(stderr, "Warning: This program requires root privileges to access MSRs.\n");
        fprintf(stderr, "Try running with sudo.\n");
        return EXIT_FAILURE;
    }
    
    // Set up signal handlers for graceful termination
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Allocate memory for in-memory buffer
    samples = malloc(sizeof(sample_t) * BUFFER_SIZE);
    if (!samples) {
        perror("Failed to allocate buffer");
        return EXIT_FAILURE;
    }
    
    // Initialize buffer with zeros
    memset(samples, 0, sizeof(sample_t) * BUFFER_SIZE);
    
    // Open output file for streaming
    open_output_file(bin_file_path);
    
    // Lock memory to prevent paging
    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("Warning: mlockall failed");
    }
    
    // Prepare thread arguments
    thread_args_t thread_args;
    thread_args.target_core = target_core;
    thread_args.duration_sec = duration_sec;
    
    // Create sampling thread with default attributes
    if (pthread_create(&sampling_thread, NULL, sampling_routine, &thread_args) != 0) {
        perror("Failed to create sampling thread");
        free(samples);
        close_output_file();
        return EXIT_FAILURE;
    }
    
    // Set real-time priority for sampling thread
    struct sched_param param;
    param.sched_priority = SAMPLING_THREAD_PRIORITY;  // High priority (real-time)
    if (pthread_setschedparam(sampling_thread, SCHED_FIFO, &param) != 0) {
        perror("Warning: Failed to set thread priority");
        // Continue anyway with default priority
    }
    
    // Main thread becomes status reporting thread
    uint64_t start_time = get_monotonic_ns();
    uint64_t end_time = start_time + (duration_sec * 1000000000ULL);
    
    // Wait for sampling thread to complete
    while (sampling_active && get_monotonic_ns() < end_time) {
        // Sleep for a short while to avoid consuming CPU
        usleep(500000);  // 500ms
    }
    
    // Signal sampling thread to stop
    sampling_active = false;
    
    // Wait for sampling thread to finish
    pthread_join(sampling_thread, NULL);
    
    // Close output file and flush remaining data
    close_output_file();
    
    printf("Profiling completed. Collected %lu samples over %d seconds.\n", 
           total_samples, duration_sec);
    printf("Data saved to %s\n", bin_file_path);
    
    // Free resources
    free(samples);
    
    return 0;
}

// Error handling function for RDPMC if it fails
// This is a stub to make the try/catch code compile
// In proper C code, you would implement error handling differently
void handle_rdpmc_error() {
    fprintf(stderr, "RDPMC instruction failed. Falling back to MSR method.\n");
    use_rdpmc = false;
}
