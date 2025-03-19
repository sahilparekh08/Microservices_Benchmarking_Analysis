#ifndef _MSR_CONSTANTS_H
#define _MSR_CONSTANTS_H

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

#endif /* _MSR_CONSTANTS_H */ 