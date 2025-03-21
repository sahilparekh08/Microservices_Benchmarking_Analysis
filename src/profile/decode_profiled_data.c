#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <dirent.h>
#include "profile_core.h"

#define CHUNK_SIZE 1000  // Number of samples to process at once

int process_profile_data(char* input_file) {
    FILE *f_in = fopen(input_file, "rb");
    if (!f_in) {
        perror("Error opening input file");
        return EXIT_FAILURE;
    }

    char output_file[2048];
    char *core_str = strstr(input_file, "core_");
    if (!core_str) {
        printf("Error: Invalid input file name\n");
        fclose(f_in);
        return EXIT_FAILURE;
    }
    snprintf(output_file, sizeof(output_file), "%.*s%s%s.csv", 
             (int)(core_str - input_file), input_file, CSV_PROFILE_DATA_FILE_PREFIX, core_str + 5);
    
    // Open output file
    FILE *f_out = fopen(output_file, "w");
    if (!f_out) {
        perror("Error opening output file");
        fclose(f_in);
        return EXIT_FAILURE;
    }
    
    // Write CSV header
    fprintf(f_out, "Time,LLC-loads,LLC-misses,Instructions\n");
    
    // Allocate memory for a chunk of samples
    sample_t *chunk = malloc(CHUNK_SIZE * sizeof(sample_t));
    if (!chunk) {
        perror("Memory allocation failed for chunk");
        fclose(f_in);
        fclose(f_out);
        return EXIT_FAILURE;
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

    return EXIT_SUCCESS;
}

int main(int argc, char *argv[]) {
    if (argc != 3) { 
        printf("Usage: %s --data-dir <dir>\n", argv[0]);
        printf("  --data-dir: directory containing profile data bin files\n");
        return EXIT_FAILURE;
    }
    
    // Parse command line arguments
    const char *data_dir = NULL;
    
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 >= argc) {
            printf("Error: Missing value for argument %s\n", argv[i]);
            return EXIT_FAILURE;
        }
        
        if (strcmp(argv[i], "--data-dir") == 0) {
            data_dir = argv[i + 1];
        } else {
            printf("Error: Unknown argument %s\n", argv[i]);
            return EXIT_FAILURE;
        }
    }
    
    // Validate required arguments
    if (!data_dir) {
        printf("Error: Data directory is required\n");
        return EXIT_FAILURE;
    }

    // TRead the directory and process each file
    DIR *dir = opendir(data_dir);
    if (!dir) {
        perror("Error opening data directory");
        return EXIT_FAILURE;
    }

    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        // Skip hidden files
        if (entry->d_name[0] == '.') {
            continue;
        }
        
        // Check if file is a profile data file
        if (strstr(entry->d_name, PROFILE_DATA_FILE_SUFFIX) == NULL) {
            continue;
        }
        
        // Process the file
        char bin_file_path[2048];
        snprintf(bin_file_path, sizeof(bin_file_path), "%s/%s", data_dir, entry->d_name);
        int ret = process_profile_data(bin_file_path);
        if (ret != EXIT_SUCCESS) {
            printf("Error processing file: %s\n", bin_file_path);
        }
    }
    
    return 0;
}