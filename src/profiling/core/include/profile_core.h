#ifndef PROFILE_CORE_H
#define PROFILE_CORE_H

#include <stdint.h>
#include <time.h>

// Output file naming
#define PROFILE_DATA_PREFIX "profile_data_"

/**
 * Structure to hold performance counter samples
 */
typedef struct {
    uint64_t monotonic_time;  // Monotonic clock time in nanoseconds
    uint64_t real_time;       // Real clock time in nanoseconds
    uint64_t llc_loads;       // LLC loads counter delta
    uint64_t llc_misses;      // LLC misses counter delta
    uint64_t instr_retired;   // Instructions retired counter delta
    int core_id;
} sample_t;

#endif /* _PROFILE_CORE_H */