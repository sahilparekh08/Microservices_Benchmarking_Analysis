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
#include <getopt.h>
#include <ctype.h>
#include <limits.h>
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
#define MAX_CORES 64         // Support up to 64 cores

// Uncomment to print performance statistics every second
// #define PRINT_STATS_EVERY_SECOND 1

// Global variables
typedef struct {
    sample_t *mapped_file;
    uint64_t total_samples;
    size_t file_size;
    int output_file_fd;
    int msr_fd;
    
    // Counter values
    uint64_t prev_llc_loads;
    uint64_t prev_llc_misses;
    uint64_t prev_instr_retired;
} core_profiler_t;

core_profiler_t core_profilers[MAX_CORES];
int num_target_cores = 0;
int target_cores[MAX_CORES];
volatile int should_exit = 0;

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

// Setup PMU counters for a specific core
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

// Open output file for a core and prepare for memory mapping
void open_output_file(const char *dir, int core_id, uint64_t max_samples, int idx) {
    char filename[PATH_MAX];
    snprintf(filename, sizeof(filename), "%s/core_%d.bin", dir, core_id);
    
    core_profilers[idx].output_file_fd = open(filename, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (core_profilers[idx].output_file_fd == -1) {
        perror("Error opening output file");
        exit(EXIT_FAILURE);
    }
    
    // Set file size
    core_profilers[idx].file_size = sizeof(sample_t) * max_samples;
    if (ftruncate(core_profilers[idx].output_file_fd, core_profilers[idx].file_size) == -1) {
        perror("Error setting file size");
        close(core_profilers[idx].output_file_fd);
        exit(EXIT_FAILURE);
    }
    
    // Map the file into memory - use MAP_POPULATE to preload pages
    core_profilers[idx].mapped_file = mmap(NULL, core_profilers[idx].file_size, PROT_WRITE, 
                                           MAP_SHARED | MAP_POPULATE, core_profilers[idx].output_file_fd, 0);
    if (core_profilers[idx].mapped_file == MAP_FAILED) {
        perror("Error mapping file");
        close(core_profilers[idx].output_file_fd);
        exit(EXIT_FAILURE);
    }
    
    // Advise kernel about our access pattern
    madvise(core_profilers[idx].mapped_file, core_profilers[idx].file_size, MADV_SEQUENTIAL);
    
    // Initialize samples count
    core_profilers[idx].total_samples = 0;
}

// Finalize output files for all cores
void close_output_files() {
    for (int i = 0; i < num_target_cores; i++) {
        if (core_profilers[i].mapped_file != MAP_FAILED && core_profilers[i].mapped_file != NULL) {
            // Resize file to match actual samples
            if (ftruncate(core_profilers[i].output_file_fd, sizeof(sample_t) * core_profilers[i].total_samples) == -1) {
                perror("Warning: Error resizing output file");
            }
            
            // Unmap memory
            if (munmap(core_profilers[i].mapped_file, core_profilers[i].file_size) == -1) {
                perror("Warning: Error unmapping file");
            }
            core_profilers[i].mapped_file = NULL;
        }
        
        if (core_profilers[i].output_file_fd != -1) {
            close(core_profilers[i].output_file_fd);
            core_profilers[i].output_file_fd = -1;
        }
        
        if (core_profilers[i].msr_fd != -1) {
            // Disable counters before closing
            write_msr(core_profilers[i].msr_fd, IA32_PERF_GLOBAL_CTRL, 0);
            close(core_profilers[i].msr_fd);
            core_profilers[i].msr_fd = -1;
        }
    }
}

// Parse comma-separated list of cores
void parse_core_list(const char *cores_str) {
    char *cores_copy = strdup(cores_str);
    char *token, *saveptr;
    
    // Reset target cores count
    num_target_cores = 0;
    
    // Parse comma-separated list
    token = strtok_r(cores_copy, ",", &saveptr);
    while (token != NULL && num_target_cores < MAX_CORES) {
        // Skip any whitespace
        while (isspace(*token)) token++;
        
        // Parse core number
        int core = atoi(token);
        target_cores[num_target_cores++] = core;
        
        // Get next token
        token = strtok_r(NULL, ",", &saveptr);
    }
    
    free(cores_copy);
    
    if (num_target_cores == 0) {
        fprintf(stderr, "Error: No valid target cores specified\n");
        exit(EXIT_FAILURE);
    }
}

// Signal handler
void signal_handler(int signum) {
    printf("\nReceived signal %d. Will exit after current batch.\n", signum);
    should_exit = 1;
}

int main(int argc, char *argv[]) {
    int core_to_pin = -1;
    int duration_sec = 0;
    char *target_cores_str = NULL;
    char *data_dir = NULL;
    
    // Define long options
    static struct option long_options[] = {
        {"core-to-pin", required_argument, 0, 'p'},
        {"target-cores", required_argument, 0, 't'},
        {"duration", required_argument, 0, 'd'},
        {"data-dir", required_argument, 0, 'o'},
        {0, 0, 0, 0}
    };
    
    // Parse command-line arguments
    int opt, option_index = 0;
    while ((opt = getopt_long(argc, argv, "p:t:d:o:", long_options, &option_index)) != -1) {
        switch (opt) {
            case 'p':
                core_to_pin = atoi(optarg);
                break;
            case 't':
                target_cores_str = optarg;
                break;
            case 'd':
                duration_sec = atoi(optarg);
                break;
            case 'o':
                data_dir = optarg;
                break;
            default:
                fprintf(stderr, "Unknown option: %c\n", opt);
                goto usage;
        }
    }
    
    // Validate required parameters
    if (core_to_pin < 0 || target_cores_str == NULL || duration_sec <= 0 || data_dir == NULL) {
        goto usage;
    }
    
    // Parse the target cores list
    parse_core_list(target_cores_str);
    
    printf("Ultra-High-Performance Multi-Core Profiler started. PID: %d\n", getpid());
    printf("Settings: pinned to core [%d], profiling %d cores, for duration [%d sec]\n", 
           core_to_pin, num_target_cores, duration_sec);
    printf("Target cores: ");
    for (int i = 0; i < num_target_cores; i++) {
        printf("%d ", target_cores[i]);
    }
    printf("\n");
    
    // Check if the output directory exists, create if needed
    struct stat st = {0};
    if (stat(data_dir, &st) == -1) {
        if (mkdir(data_dir, 0755) == -1) {
            perror("Error creating output directory");
            return EXIT_FAILURE;
        }
    }
    
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
    
    // Initialize all core profilers
    memset(core_profilers, 0, sizeof(core_profilers));
    for (int i = 0; i < num_target_cores; i++) {
        // Open MSR device for this core
        core_profilers[i].msr_fd = open_msr(target_cores[i]);
        if (core_profilers[i].msr_fd < 0) {
            perror("Error opening MSR device. Try running with sudo");
            close_output_files(); // Clean up any already opened files
            return EXIT_FAILURE;
        }
        
        // Open and map output file for this core
        open_output_file(data_dir, target_cores[i], BUFFER_SIZE, i);
        
        // Setup PMU counters for this core
        setup_pmu(core_profilers[i].msr_fd);
        
        // Initialize counter values
        core_profilers[i].prev_llc_loads = read_msr(core_profilers[i].msr_fd, IA32_PMC0);
        core_profilers[i].prev_llc_misses = read_msr(core_profilers[i].msr_fd, IA32_PMC1);
        core_profilers[i].prev_instr_retired = read_msr(core_profilers[i].msr_fd, IA32_PMC2);
    }
    
    // Calculate end time
    struct timespec ts_mono, ts_real;
    clock_gettime(CLOCK_MONOTONIC, &ts_mono);
    uint64_t start_time = (uint64_t)ts_mono.tv_sec * 1000000000ULL + ts_mono.tv_nsec;
    uint64_t end_time = start_time + (duration_sec * 1000000000ULL);

    #ifdef PRINT_STATS_EVERY_SECOND
    uint64_t next_status_time = start_time + 1000000000ULL;
    uint64_t last_samples[MAX_CORES] = {0};
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
        
        #ifdef PRINT_STATS_EVERY_SECOND
        // Performance status update every second
        if (now_mono >= next_status_time) {
            printf("Samples/sec: ");
            for (int i = 0; i < num_target_cores; i++) {
                uint64_t samples_this_second = core_profilers[i].total_samples - last_samples[i];
                printf("Core %d: %lu  ", target_cores[i], samples_this_second);
                last_samples[i] = core_profilers[i].total_samples;
            }
            printf("\n");
            next_status_time += 1000000000ULL;
        }
        #endif
        
        // Process each core
        for (int i = 0; i < num_target_cores; i++) {
            core_profiler_t *prof = &core_profilers[i];
            
            // Check if we have room for more samples
            if (prof->total_samples >= BUFFER_SIZE) {
                continue;  // Skip this core, buffer is full
            }
            
            // Read counter values for this core
            uint64_t curr_llc_loads = read_msr(prof->msr_fd, IA32_PMC0);
            uint64_t curr_llc_misses = read_msr(prof->msr_fd, IA32_PMC1);
            uint64_t curr_instr_retired = read_msr(prof->msr_fd, IA32_PMC2);
            
            // Store both monotonic and real time
            prof->mapped_file[prof->total_samples].monotonic_time = now_mono;
            prof->mapped_file[prof->total_samples].real_time = now_real;
            
            // Store counter deltas directly
            prof->mapped_file[prof->total_samples].llc_loads = curr_llc_loads - prof->prev_llc_loads;
            prof->mapped_file[prof->total_samples].llc_misses = curr_llc_misses - prof->prev_llc_misses;
            prof->mapped_file[prof->total_samples].instr_retired = curr_instr_retired - prof->prev_instr_retired;
            
            // Update previous values
            prof->prev_llc_loads = curr_llc_loads;
            prof->prev_llc_misses = curr_llc_misses;
            prof->prev_instr_retired = curr_instr_retired;
            
            // Increment sample counter
            prof->total_samples++;
        }
        
        // No sleep or pause - run at absolute maximum speed
    }
    
    // Get end time
    struct timespec end_ts;
    clock_gettime(CLOCK_MONOTONIC, &end_ts);
    uint64_t actual_end_time = (uint64_t)end_ts.tv_sec * 1000000000ULL + end_ts.tv_nsec;
    double elapsed_seconds = (actual_end_time - start_time) / 1000000000.0;
    
    // Print statistics
    printf("\nProfiling complete:\n");
    printf("- Elapsed time: %.2f seconds\n", elapsed_seconds);
    printf("- Per-core statistics:\n");
    
    for (int i = 0; i < num_target_cores; i++) {
        printf("  Core %d: %lu samples (%.2f samples/second)\n", 
               target_cores[i], 
               core_profilers[i].total_samples,
               core_profilers[i].total_samples / elapsed_seconds);
    }
    
    printf("- Data saved to: %s/core_X.bin\n", data_dir);
    
    // Clean up
    close_output_files();
    
    return 0;

usage:
    printf("Usage: %s --core-to-pin <core> --target-cores <cores> --duration <seconds> --data-dir <dir>\n", argv[0]);
    printf(" --core-to-pin: core to pin the profiler to\n");
    printf(" --target-cores: comma-separated list of cores to profile (e.g., \"0,1,2\")\n");
    printf(" --duration: duration in seconds to profile\n");
    printf(" --data-dir: directory to store per-core bin files\n");
    return EXIT_FAILURE;
}