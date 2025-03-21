#ifndef _PROFILE_CORE_H
#define _PROFILE_CORE_H

#include <stdint.h>
#include <time.h>

#define CSV_PROFILE_DATA_FILE_PREFIX "profile_data_"
#define PROFILE_DATA_FILE_SUFFIX ".bin"

typedef struct {
    uint64_t monotonic_time;  // Monotonic clock time in nanoseconds
    uint64_t real_time;       // Real clock time in nanoseconds
    uint64_t llc_loads;       // LLC loads counter delta
    uint64_t llc_misses;      // LLC misses counter delta
    uint64_t instr_retired;   // Instructions retired counter delta
} sample_t;

#endif /* _PROFILE_CORE_H */