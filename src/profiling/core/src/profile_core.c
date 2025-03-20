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
#include <errno.h>
#include <limits.h>
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

// Add new structure for per-core file handling
typedef struct {
    int fd;
    sample_t* mapped_file;
    size_t file_size;
    uint64_t total_samples;
} core_file_t;

// Modify open_output_file to handle per-core files
int open_output_file(const char* base_dir, int core_id, uint64_t max_samples, core_file_t* core_file) {
    char filename[PATH_MAX];
    snprintf(filename, sizeof(filename), "%s/%s%d.bin", base_dir, PROFILE_DATA_PREFIX, core_id);
    
    core_file->fd = open(filename, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (core_file->fd == -1) {
        perror("Error opening output file");
        return -1;
    }
    
    // Set file size
    core_file->file_size = sizeof(sample_t) * max_samples;
    if (ftruncate(core_file->fd, core_file->file_size) == -1) {
        perror("Error setting file size");
        close(core_file->fd);
        return -1;
    }
    
    // Map the file into memory with MAP_POPULATE for better performance
    core_file->mapped_file = mmap(NULL, core_file->file_size, PROT_WRITE, MAP_SHARED | MAP_POPULATE, core_file->fd, 0);
    if (core_file->mapped_file == MAP_FAILED) {
        perror("Error mapping file");
        close(core_file->fd);
        return -1;
    }
    
    // Advise kernel about our access pattern
    madvise(core_file->mapped_file, core_file->file_size, MADV_SEQUENTIAL);
    
    core_file->total_samples = 0;
    return 0;
}

// Modify close_output_file to handle per-core files
void close_output_file(core_file_t* core_file) {
    if (core_file->mapped_file != MAP_FAILED && core_file->mapped_file != NULL) {
        // Resize file to match actual samples
        if (ftruncate(core_file->fd, sizeof(sample_t) * core_file->total_samples) == -1) {
            perror("Warning: Error resizing output file");
        }
        
        // Unmap memory
        if (munmap(core_file->mapped_file, core_file->file_size) == -1) {
            perror("Warning: Error unmapping file");
        }
        core_file->mapped_file = NULL;
    }
    
    if (core_file->fd != -1) {
        close(core_file->fd);
        core_file->fd = -1;
    }
}

// Signal handler
void signal_handler(int signum) {
    printf("\nReceived signal %d. Will exit after current batch.\n", signum);
    should_exit = 1;
}

// Add new structure for per-core counters
typedef struct {
    uint64_t prev_llc_loads;
    uint64_t prev_llc_misses;
    uint64_t prev_instr_retired;
    int msr_fd;
} core_counters_t;

// Function to parse comma-separated list of cores
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
    if (argc != 11) {  // 5 arguments * 2 (flag + value) + 1 (program name)
        printf("Usage: %s --core-to-pin <core> --target-coress <cores> --duration <seconds> --data-dir <dir> --max-samples <count>\n", argv[0]);
        printf("  --core-to-pin: core to pin the profiler to\n");
        printf("  --target-coress: comma-separated list of cores to profile (e.g., \"0,1,2\")\n");
        printf("  --duration: duration in seconds to profile\n");
        printf("  --data-dir: directory to store per-core bin files\n");
        printf("  --max-samples: maximum number of samples to collect per core\n");
        return EXIT_FAILURE;
    }
    
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
        } else if (strcmp(argv[i], "--max-samples") == 0) {
            max_samples_per_core = atoll(argv[i + 1]);
        } else {
            printf("Error: Unknown argument %s\n", argv[i]);
            return EXIT_FAILURE;
        }
    }
    
    // Validate arguments
    if (core_to_pin < 0 || !target_cores_str || duration_sec <= 0 || !data_dir || max_samples_per_core == 0) {
        printf("Error: All arguments are required and must be valid\n");
        return EXIT_FAILURE;
    }
    
    int* target_cores;
    int num_target_cores;
    if (parse_target_cores(target_cores_str, &target_cores, &num_target_cores) == 0) {
        printf("Error: No valid target cores specified\n");
        return EXIT_FAILURE;
    }
    
    // Create output directory if it doesn't exist
    if (mkdir(data_dir, 0755) == -1 && errno != EEXIST) {
        perror("Error creating output directory");
        free(target_cores);
        return EXIT_FAILURE;
    }
    
    printf("Ultra-High-Performance Profiler started. PID: %d\n", getpid());
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
    
    // Pin to specified core
    cpu_set_t cpu_set;
    CPU_ZERO(&cpu_set);
    CPU_SET(core_to_pin, &cpu_set);
    if (sched_setaffinity(0, sizeof(cpu_set), &cpu_set) == -1) {
        perror("Error setting CPU affinity");
        free(target_cores);
        return EXIT_FAILURE;
    }
    
    // Lock all memory
    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("Warning: mlockall failed");
    }
    
    // Open MSR devices for all target cores
    core_counters_t* core_counters = malloc(num_target_cores * sizeof(core_counters_t));
    core_file_t* core_files = malloc(num_target_cores * sizeof(core_file_t));
    
    for (int i = 0; i < num_target_cores; i++) {
        // Open MSR device
        core_counters[i].msr_fd = open_msr(target_cores[i]);
        if (core_counters[i].msr_fd < 0) {
            printf("Error opening MSR device for core %d. Try running with sudo\n", target_cores[i]);
            // Cleanup
            for (int j = 0; j < i; j++) {
                close(core_counters[j].msr_fd);
                close_output_file(&core_files[j]);
            }
            free(core_counters);
            free(core_files);
            free(target_cores);
            return EXIT_FAILURE;
        }
        
        // Open output file for this core
        if (open_output_file(data_dir, target_cores[i], max_samples_per_core, &core_files[i]) == -1) {
            printf("Error opening output file for core %d\n", target_cores[i]);
            // Cleanup
            for (int j = 0; j <= i; j++) {
                close(core_counters[j].msr_fd);
                close_output_file(&core_files[j]);
            }
            free(core_counters);
            free(core_files);
            free(target_cores);
            return EXIT_FAILURE;
        }
        
        // Initialize previous counter values
        core_counters[i].prev_llc_loads = read_msr(core_counters[i].msr_fd, IA32_PMC0);
        core_counters[i].prev_llc_misses = read_msr(core_counters[i].msr_fd, IA32_PMC1);
        core_counters[i].prev_instr_retired = read_msr(core_counters[i].msr_fd, IA32_PMC2);
    }
    
    // Setup PMU counters for all cores
    for (int i = 0; i < num_target_cores; i++) {
        setup_pmu(core_counters[i].msr_fd);
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
        
        // Read counter values from all cores
        for (int i = 0; i < num_target_cores; i++) {
            if (core_files[i].total_samples >= max_samples_per_core) {
                printf("Buffer full for core %d at %lu samples, stopping\n", target_cores[i], core_files[i].total_samples);
                goto cleanup;
            }
            
            uint64_t curr_llc_loads = read_msr(core_counters[i].msr_fd, IA32_PMC0);
            uint64_t curr_llc_misses = read_msr(core_counters[i].msr_fd, IA32_PMC1);
            uint64_t curr_instr_retired = read_msr(core_counters[i].msr_fd, IA32_PMC2);
            
            // Store both monotonic and real time
            core_files[i].mapped_file[core_files[i].total_samples].monotonic_time = now_mono;
            core_files[i].mapped_file[core_files[i].total_samples].real_time = now_real;
            
            // Store counter deltas directly
            core_files[i].mapped_file[core_files[i].total_samples].llc_loads = curr_llc_loads - core_counters[i].prev_llc_loads;
            core_files[i].mapped_file[core_files[i].total_samples].llc_misses = curr_llc_misses - core_counters[i].prev_llc_misses;
            core_files[i].mapped_file[core_files[i].total_samples].instr_retired = curr_instr_retired - core_counters[i].prev_instr_retired;
            
            // Store core ID
            core_files[i].mapped_file[core_files[i].total_samples].core_id = target_cores[i];
            
            // Update previous values
            core_counters[i].prev_llc_loads = curr_llc_loads;
            core_counters[i].prev_llc_misses = curr_llc_misses;
            core_counters[i].prev_instr_retired = curr_instr_retired;
            
            // Increment sample counter
            core_files[i].total_samples++;
        }
        
        // No sleep or pause - run at absolute maximum speed
    }
    
cleanup:
    // Disable counters and close MSR devices for all cores
    for (int i = 0; i < num_target_cores; i++) {
        write_msr(core_counters[i].msr_fd, IA32_PERF_GLOBAL_CTRL, 0);
        close(core_counters[i].msr_fd);
        close_output_file(&core_files[i]);
    }
    
    // Print statistics
    struct timespec end_ts;
    clock_gettime(CLOCK_MONOTONIC, &end_ts);
    uint64_t actual_end_time = (uint64_t)end_ts.tv_sec * 1000000000ULL + end_ts.tv_nsec;
    double elapsed_seconds = (actual_end_time - start_time) / 1000000000.0;
    
    printf("\nProfiling complete:\n");
    printf("- Elapsed time: %.2f seconds\n", elapsed_seconds);
    for (int i = 0; i < num_target_cores; i++) {
        printf("- Core %d: %lu samples (%.2f samples/second)\n", 
               target_cores[i], 
               core_files[i].total_samples,
               core_files[i].total_samples / elapsed_seconds);
    }
    printf("- Data saved to: %s\n", data_dir);
    
    // Clean up
    free(core_counters);
    free(core_files);
    free(target_cores);
    
    return 0;
}