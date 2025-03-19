#ifndef _PROFILE_CORE_H
#define _PROFILE_CORE_H

#include <stdint.h>
#include <time.h>

/**
 * Structure to hold performance counter samples
 */
typedef struct {
    uint64_t monotonic_time;  // Monotonic clock time in nanoseconds
    uint64_t real_time;       // Real clock time in nanoseconds
    uint64_t llc_loads;       // LLC loads counter delta
    uint64_t llc_misses;      // LLC misses counter delta
    uint64_t instr_retired;   // Instructions retired counter delta
} sample_t;

/**
 * Sets up the Performance Monitoring Unit (PMU) counters
 * @param msr_fd File descriptor for MSR device
 * @return 0 on success, -1 on failure
 */
int setup_pmu(int msr_fd);

/**
 * Opens and prepares an output file for memory mapping
 * @param filename Path to the output file
 * @param max_samples Maximum number of samples to store
 * @return 0 on success, -1 on failure
 */
int open_output_file(const char *filename, uint64_t max_samples);

/**
 * Closes and finalizes the output file
 */
void close_output_file(void);

/**
 * Signal handler for graceful shutdown
 * @param signum Signal number received
 */
void signal_handler(int signum);

#endif /* _PROFILE_CORE_H */