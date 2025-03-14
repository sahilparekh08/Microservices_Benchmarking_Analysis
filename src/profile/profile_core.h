#ifndef _PROFILE_CORE_H
#define _PROFILE_CORE_H

#include <stdint.h>
#include <time.h>

typedef struct {
    struct timespec real_time;  // Real timestamp (seconds + nanoseconds)
    uint64_t monotonic_time;    // Monotonic time in nanoseconds (for precise intervals)
    uint64_t llc_loads;
    uint64_t llc_misses;
    uint64_t instr_retired;
} sample_t;

#endif /* _PROFILE_CORE_H */