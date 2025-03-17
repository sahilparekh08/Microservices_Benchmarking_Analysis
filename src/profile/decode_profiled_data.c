#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "profile_core.h"

#define CHUNK_SIZE 1000  // Number of samples to process at once

int main(int argc, char *argv[]) {
    if (argc < 2 || argc > 3) {
        fprintf(stderr, "Usage: %s <data_file> [output_file.csv]\n", argv[0]);
        return 1;
    }
    
    const char *input_file = argv[1];
    const char *output_file = (argc == 3) ? argv[2] : "profiling_results.csv";
    
    FILE *f_in = fopen(input_file, "rb");
    if (!f_in) {
        perror("Error opening input file");
        return 1;
    }
    
    // Open output file
    FILE *f_out = fopen(output_file, "w");
    if (!f_out) {
        perror("Error opening output file");
        fclose(f_in);
        return 1;
    }
    
    // Write CSV header
    fprintf(f_out, "Time,LLC-loads,LLC-misses,Instructions\n");
    
    // Allocate memory for a chunk of samples
    sample_t *chunk = malloc(CHUNK_SIZE * sizeof(sample_t));
    if (!chunk) {
        perror("Memory allocation failed for chunk");
        fclose(f_in);
        fclose(f_out);
        return 1;
    }
    
    // Read and process in chunks
    long samples_processed = 0;
    size_t samples_read;
    
    while ((samples_read = fread(chunk, sizeof(sample_t), CHUNK_SIZE, f_in)) > 0) {        
        // Process each sample in the chunk
        for (size_t i = 0; i < samples_read; i++) {
            // Convert real timestamp to microseconds
            uint64_t time_us = chunk[i].real_time / 1000;
            
            // Write to CSV
            fprintf(f_out, "%lu,%lu,%lu,%lu\n", 
                    time_us, 
                    chunk[i].llc_loads, 
                    chunk[i].llc_misses, 
                    chunk[i].instr_retired);
        }
        
        samples_processed += samples_read;
    }
    
    // Free resources
    free(chunk);
    fclose(f_in);
    fclose(f_out);
    
    printf("Successfully wrote %ld samples to %s\n", samples_processed, output_file);
    
    return 0;
}