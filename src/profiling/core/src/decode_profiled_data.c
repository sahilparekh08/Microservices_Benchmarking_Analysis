#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include "profile_core.h"

#define DEFAULT_CHUNK_SIZE 1000  // Default number of samples to process at once
#define MAX_CHUNK_SIZE 1000000   // Maximum allowed chunk size

static void print_usage(const char *program_name) {
    fprintf(stderr, "Usage: %s <data_file> [output_file.csv] [chunk_size]\n", program_name);
    fprintf(stderr, "  data_file: Input binary file containing profiling data\n");
    fprintf(stderr, "  output_file.csv: Optional output CSV file (default: profiling_results.csv)\n");
    fprintf(stderr, "  chunk_size: Optional number of samples to process at once (default: %d, max: %d)\n",
            DEFAULT_CHUNK_SIZE, MAX_CHUNK_SIZE);
}

static int validate_chunk_size(size_t chunk_size) {
    if (chunk_size == 0 || chunk_size > MAX_CHUNK_SIZE) {
        fprintf(stderr, "Error: Chunk size must be between 1 and %d\n", MAX_CHUNK_SIZE);
        return -1;
    }
    return 0;
}

static FILE *safe_fopen(const char *filename, const char *mode) {
    FILE *fp = fopen(filename, mode);
    if (!fp) {
        fprintf(stderr, "Error opening file '%s': %s\n", filename, strerror(errno));
    }
    return fp;
}

int main(int argc, char *argv[]) {
    if (argc < 2 || argc > 4) {
        print_usage(argv[0]);
        return 1;
    }
    
    const char *input_file = argv[1];
    const char *output_file = (argc >= 3) ? argv[2] : "profiling_results.csv";
    size_t chunk_size = DEFAULT_CHUNK_SIZE;
    
    if (argc == 4) {
        char *endptr;
        chunk_size = strtoul(argv[3], &endptr, 10);
        if (*endptr != '\0' || validate_chunk_size(chunk_size) != 0) {
            print_usage(argv[0]);
            return 1;
        }
    }
    
    FILE *f_in = safe_fopen(input_file, "rb");
    if (!f_in) {
        return 1;
    }
    
    FILE *f_out = safe_fopen(output_file, "w");
    if (!f_out) {
        fclose(f_in);
        return 1;
    }
    
    // Write CSV header
    if (fprintf(f_out, "Time,LLC-loads,LLC-misses,Instructions\n") < 0) {
        fprintf(stderr, "Error writing CSV header: %s\n", strerror(errno));
        fclose(f_in);
        fclose(f_out);
        return 1;
    }
    
    // Allocate memory for a chunk of samples
    sample_t *chunk = malloc(chunk_size * sizeof(sample_t));
    if (!chunk) {
        fprintf(stderr, "Memory allocation failed for chunk: %s\n", strerror(errno));
        fclose(f_in);
        fclose(f_out);
        return 1;
    }
    
    // Read and process in chunks
    long samples_processed = 0;
    size_t samples_read;
    int error_occurred = 0;
    
    while (!error_occurred && (samples_read = fread(chunk, sizeof(sample_t), chunk_size, f_in)) > 0) {
        // Process each sample in the chunk
        for (size_t i = 0; i < samples_read; i++) {
            // Convert real timestamp to microseconds
            uint64_t time_us = chunk[i].real_time / 1000;
            
            // Write to CSV
            if (fprintf(f_out, "%lu,%lu,%lu,%lu\n", 
                    time_us, 
                    chunk[i].llc_loads, 
                    chunk[i].llc_misses, 
                    chunk[i].instr_retired) < 0) {
                fprintf(stderr, "Error writing to CSV: %s\n", strerror(errno));
                error_occurred = 1;
                break;
            }
        }
        
        samples_processed += samples_read;
    }
    
    if (error_occurred) {
        fprintf(stderr, "Error occurred while processing samples\n");
    } else if (ferror(f_in)) {
        fprintf(stderr, "Error reading input file: %s\n", strerror(errno));
    }
    
    // Free resources
    free(chunk);
    fclose(f_in);
    fclose(f_out);
    
    if (!error_occurred) {
        printf("Successfully wrote %ld samples to %s\n", samples_processed, output_file);
    }
    
    return error_occurred ? 1 : 0;
}