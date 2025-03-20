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
#define BUFFER_SIZE 50000000 // Allow up to 50 million samples in memory

// Uncomment to print performance statistics every second
// #define PRINT_STATS_EVERY_SECOND 1

// Global variables
volatile int should_exit = 0;

typedef struct core_profile_data {
    sample_t* mapped_file;
    uint64_t total_samples;
    size_t file_size;
    int output_file_fd;
    char output_file_path[2048];
} core_profile_data_t;

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

// Open output file and prepare for memory mapping
int open_output_file(const char *filename, uint64_t max_samples, core_profile_data_t* core_data) {
    int output_file_fd;
    sample_t* mapped_file;
    size_t file_size;

    output_file_fd = open(filename, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (output_file_fd == -1) {
        perror("Error opening output file");
        return EXIT_FAILURE;
    }
    
    // Set file size
    file_size = sizeof(sample_t) * max_samples;
    if (ftruncate(output_file_fd, file_size) == -1) {
        perror("Error setting file size");
        close(output_file_fd);
        return EXIT_FAILURE;
    }
    
    // Map the file into memory - use MAP_POPULATE to preload pages
    mapped_file = mmap(NULL, file_size, PROT_WRITE, MAP_SHARED | MAP_POPULATE, output_file_fd, 0);
    if (mapped_file == MAP_FAILED) {
        perror("Error mapping file");
        close(output_file_fd);
        return EXIT_FAILURE;
    }
    
    // Advise kernel about our access pattern
    madvise(mapped_file, file_size, MADV_SEQUENTIAL);

    // Store the file descriptor and mapped memory
    core_data->mapped_file = mapped_file;
    core_data->total_samples = 0;
    core_data->file_size = file_size;
    core_data->output_file_fd = output_file_fd;

    return EXIT_SUCCESS;
}

// Finalize output file
void close_output_file(core_profile_data_t** core_data) {
    sample_t* mapped_file = (*core_data)->mapped_file;
    size_t file_size = (*core_data)->file_size;
    uint64_t total_samples = (*core_data)->total_samples;
    int output_file_fd = (*core_data)->output_file_fd;

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

// Retrieve cores from comma separated core list
int parse_target_cores(const char* cores_str, int** target_cores, int* num_cores) {
    char* str = strdup(cores_str);
    char* token = strtok(str, ",");
    int count = 0;
    int capacity = 10;  // Initial capacity
    *target_cores = malloc(capacity * sizeof(int));
    
    while (token != NULL) {
        if (count >= capacity) {
            capacity *= 2;
            *target_cores = realloc(*target_cores, capacity * sizeof(int));
        }
        (*target_cores)[count++] = atoi(token);
        token = strtok(NULL, ",");
    }
    
    *num_cores = count;
    free(str);
    return count;
}

int main(int argc, char *argv[]) {
    if (argc < 9 || argc > 11) {
        printf("Usage: %s --core-to-pin <core> --target-cores <cores> --duration <seconds> --data-dir <dir>\n", argv[0]);
        printf("  --core-to-pin: core to pin the profiler to\n");
        printf("  --target-cores: comma-separated list of cores to profile (e.g., \"0,1,2\")\n");
        printf("  --duration: duration in seconds to profile\n");
        printf("  --data-dir: directory to store per-core bin files\n");
        return EXIT_FAILURE;
    }

    int ret = EXIT_SUCCESS;
    
    // Parse command line arguments
    int core_to_pin = -1;
    char *target_cores_str = NULL;
    int duration_sec = -1;
    const char *data_dir = NULL;
    uint64_t max_samples_per_core = BUFFER_SIZE;
    
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 >= argc) {
            printf("Error: Missing value for argument %s\n", argv[i]);
            return EXIT_FAILURE;
        }
        
        if (strcmp(argv[i], "--core-to-pin") == 0) {
            core_to_pin = atoi(argv[i + 1]);
        } else if (strcmp(argv[i], "--target-cores") == 0) {
            target_cores_str = argv[i + 1];
        } else if (strcmp(argv[i], "--duration") == 0) {
            duration_sec = atoi(argv[i + 1]);
        } else if (strcmp(argv[i], "--data-dir") == 0) {
            data_dir = argv[i + 1];
        } else {
            printf("Error: Unknown argument %s\n", argv[i]);
            return EXIT_FAILURE;
        }
    }
    
    // Validate arguments
    if (core_to_pin < 0 || !target_cores_str || duration_sec <= 0 || !data_dir) {
        printf("Error: All arguments are required and must be valid\n");
        return EXIT_FAILURE;
    }
    
    int* target_cores;
    int num_target_cores;
    if (parse_target_cores(target_cores_str, &target_cores, &num_target_cores) == 0) {
        printf("Error: No valid target cores specified\n");
        return EXIT_FAILURE;
    }
    
    printf("Profiler started. PID: %d\n", getpid());
    printf("Settings: pinned to core [%d], profiling %d cores [", core_to_pin, num_target_cores);
    for (int i = 0; i < num_target_cores; i++) {
        printf("%d%s", target_cores[i], i < num_target_cores - 1 ? "," : "");
    }
    printf("], for duration [%d sec]\n", duration_sec);
    printf("Output directory: %s\n", data_dir);
    printf("Max samples per core: %lu\n", max_samples_per_core);
    
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

    // Allocate memory for each core's profile data
    core_profile_data_t* core_data = malloc(num_target_cores * sizeof(core_profile_data_t));
    for (int i = 0; i < num_target_cores; i++) {
        core_data[i].mapped_file = NULL;
        core_data[i].total_samples = 0;
        core_data[i].file_size = 0;
        core_data[i].output_file_fd = -1;
    }
    uint64_t* prev_llc_loads = NULL;
    uint64_t* prev_llc_misses = NULL;
    uint64_t* prev_instr_retired = NULL;

    // Open all MSR devices for target cores
    int* msr_fds = malloc(num_target_cores * sizeof(int));
    for (int i = 0; i < num_target_cores; i++) {
        msr_fds[i] = open_msr(target_cores[i]);
        if (msr_fds[i] < 0) {
            perror("Error opening MSR device. Try running with sudo");
            goto failure;
        }
    }
    
    // Open and map output files for all target cores
    for (int i = 0; i < num_target_cores; i++) {
        char bin_file_path[2048];
        snprintf(bin_file_path, sizeof(bin_file_path), "%s/%score_%d%s", data_dir, PROFILE_DATA_FILE_PREFIX, target_cores[i], PROFILE_DATA_FILE_SUFFIX);
        if(open_output_file(bin_file_path, max_samples_per_core, &core_data[i]) == EXIT_FAILURE) {
            goto failure;
        }
        strcpy(core_data[i].output_file_path, bin_file_path);
    }

    // Setup PMU counters for all target cores
    for (int i = 0; i < num_target_cores; i++) {
        setup_pmu(msr_fds[i]);
    }
    
    // Calculate end time
    struct timespec ts_mono, ts_real;
    clock_gettime(CLOCK_MONOTONIC, &ts_mono);
    uint64_t start_time = (uint64_t)ts_mono.tv_sec * 1000000000ULL + ts_mono.tv_nsec;
    uint64_t end_time = start_time + (duration_sec * 1000000000ULL);

#ifdef PRINT_STATS_EVERY_SECOND
    uint64_t next_status_time = start_time + 1000000000ULL;
    uint64_t last_samples = 0;
#endif

    // Initialize performance counter values
    prev_llc_loads = malloc(num_target_cores * sizeof(uint64_t));
    prev_llc_misses = malloc(num_target_cores * sizeof(uint64_t));
    prev_instr_retired = malloc(num_target_cores * sizeof(uint64_t));
    for (int i = 0; i < num_target_cores; i++) {
        prev_llc_loads[i] = read_msr(msr_fds[i], IA32_PMC0);
        prev_llc_misses[i] = read_msr(msr_fds[i], IA32_PMC1);
        prev_instr_retired[i] = read_msr(msr_fds[i], IA32_PMC2);
    }
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

        // Loop through all target cores
        for (int i = 0; i < num_target_cores; i++) {
            // Read counter values - done in one tight block to minimize time between reads
            curr_llc_loads = read_msr(msr_fds[i], IA32_PMC0);
            curr_llc_misses = read_msr(msr_fds[i], IA32_PMC1);
            curr_instr_retired = read_msr(msr_fds[i], IA32_PMC2);
            
            // Store both monotonic and real time
            core_data[i].mapped_file[core_data[i].total_samples].monotonic_time = now_mono;
            core_data[i].mapped_file[core_data[i].total_samples].real_time = now_real;
            
            // Store counter deltas directly
            core_data[i].mapped_file[core_data[i].total_samples].llc_loads = curr_llc_loads - prev_llc_loads[i];
            core_data[i].mapped_file[core_data[i].total_samples].llc_misses = curr_llc_misses - prev_llc_misses[i];
            core_data[i].mapped_file[core_data[i].total_samples].instr_retired = curr_instr_retired - prev_instr_retired[i];
            
            // Update previous values
            prev_llc_loads[i] = curr_llc_loads;
            prev_llc_misses[i] = curr_llc_misses;
            prev_instr_retired[i] = curr_instr_retired;
            
            // Increment sample counter
            core_data[i].total_samples++;
            
            // Check for buffer overflow
            if (core_data[i].total_samples >= max_samples_per_core) {
                printf("Buffer full at %lu samples, stopping\n", core_data[i].total_samples);
                break;
            }
        }
        
        // No sleep or pause
    }
    
    // Disable counters
    for (int i = 0; i < num_target_cores; i++) {
        write_msr(msr_fds[i], IA32_PERF_GLOBAL_CTRL, 0);
    }
    
    // Close MSR devices
    for (int i = 0; i < num_target_cores; i++) {
        close(msr_fds[i]);
    }
    
    // Print statistics
    struct timespec end_ts;
    clock_gettime(CLOCK_MONOTONIC, &end_ts);
    uint64_t actual_end_time = (uint64_t)end_ts.tv_sec * 1000000000ULL + end_ts.tv_nsec;
    double elapsed_seconds = (actual_end_time - start_time) / 1000000000.0;

    printf("\nProfiling complete:\n");
    printf("- Elapsed time: %.2f seconds\n", elapsed_seconds);
    for (int i = 0; i < num_target_cores; i++) {
        printf("Core %d:\n", target_cores[i]);
        printf("  - Samples: %lu\n", core_data[i].total_samples);
        printf("  - Average sampling rate: %.2f samples/second\n", core_data[i].total_samples / elapsed_seconds);
        printf("  - Data saved to: %s\n", core_data[i].output_file_path);
    }

    goto cleanup;

failure:
    ret = EXIT_FAILURE;
    
cleanup:
    // Free resources
    close_output_file(&core_data);
    free(core_data);
    free(msr_fds);
    free(prev_llc_loads);
    free(prev_llc_misses);
    free(prev_instr_retired);
    free(target_cores);
    
    return ret;
}