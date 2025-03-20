#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <limits.h>
#include "../include/profile_core.h"

#define DEFAULT_CHUNK_SIZE 1000  // Default number of samples to process at once
#define MAX_CHUNK_SIZE 1000000   // Maximum allowed chunk size
#define MAX_FILENAME_LEN 2048    // Increased maximum length for filenames

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

static int process_file(const char *input_file, const char *output_file, size_t chunk_size) {
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
    
    // Check for read errors
    if (ferror(f_in)) {
        fprintf(stderr, "Error reading input file: %s\n", strerror(errno));
        error_occurred = 1;
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

static int is_profile_data_file(const char *filename) {
    return strncmp(filename, PROFILE_DATA_PREFIX, strlen(PROFILE_DATA_PREFIX)) == 0 &&
           strcmp(filename + strlen(filename) - 4, ".bin") == 0;
}

static int extract_core_id(const char *filename) {
    // Extract core ID from filename (profile_data_<core_id>.bin)
    const char *core_id_str = filename + strlen(PROFILE_DATA_PREFIX);
    char *endptr;
    int core_id = strtol(core_id_str, &endptr, 10);
    
    if (*endptr != '.' || strcmp(endptr, ".bin") != 0) {
        return -1;
    }
    
    return core_id;
}

int main(int argc, char *argv[]) {
    if (argc < 3 || argc > 5) { 
        printf("Usage: %s --data-dir <dir> [--chunk-size <size>]\n", argv[0]);
        printf("  --data-dir: directory containing profile data bin files\n");
        printf("  --chunk-size: optional number of samples to process at once (default: %d, max: %d)\n",
                DEFAULT_CHUNK_SIZE, MAX_CHUNK_SIZE);
        return EXIT_FAILURE;
    }
    
    // Parse command line arguments
    const char *data_dir = NULL;
    size_t chunk_size = DEFAULT_CHUNK_SIZE;
    
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 >= argc) {
            printf("Error: Missing value for argument %s\n", argv[i]);
            return EXIT_FAILURE;
        }
        
        if (strcmp(argv[i], "--data-dir") == 0) {
            data_dir = argv[i + 1];
        } else if (strcmp(argv[i], "--chunk-size") == 0) {
            char *endptr;
            chunk_size = strtoul(argv[i + 1], &endptr, 10);
            if (*endptr != '\0' || validate_chunk_size(chunk_size) != 0) {
                return EXIT_FAILURE;
            }
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
    
    // Open input directory
    DIR *dir = opendir(data_dir);
    if (!dir) {
        fprintf(stderr, "Error opening input directory '%s': %s\n", data_dir, strerror(errno));
        return EXIT_FAILURE;
    }
    
    struct dirent *entry;
    int total_files = 0;
    int processed_files = 0;
    int error_occurred = 0;
    
    // Process each file in the directory
    while ((entry = readdir(dir)) != NULL) {
        // Skip . and .. entries
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        
        // Check if file starts with PROFILE_DATA_PREFIX
        if (!is_profile_data_file(entry->d_name)) {
            continue;
        }
        
        // Check if it's a regular file
        char full_path[MAX_FILENAME_LEN];
        int path_len = snprintf(full_path, sizeof(full_path), "%s/%s", data_dir, entry->d_name);
        if (path_len >= sizeof(full_path) || path_len < 0) {
            fprintf(stderr, "Path too long or encoding error: %s/%s\n", data_dir, entry->d_name);
            error_occurred = 1;
            continue;
        }
        
        struct stat st;
        if (stat(full_path, &st) != 0 || !S_ISREG(st.st_mode)) {
            fprintf(stderr, "Warning: Skipping non-regular file '%s'\n", entry->d_name);
            continue;
        }
        
        total_files++;
        
        // Extract core ID from filename
        int core_id = extract_core_id(entry->d_name);
        if (core_id == -1) {
            fprintf(stderr, "Warning: Skipping invalid filename '%s'\n", entry->d_name);
            continue;
        }
        
        // Construct full paths
        char input_path[MAX_FILENAME_LEN];
        char output_path[MAX_FILENAME_LEN];
        
        path_len = snprintf(input_path, sizeof(input_path), "%s/%s", data_dir, entry->d_name);
        if (path_len >= sizeof(input_path) || path_len < 0) {
            fprintf(stderr, "Path too long or encoding error: %s/%s\n", data_dir, entry->d_name);
            error_occurred = 1;
            continue;
        }
        
        path_len = snprintf(output_path, sizeof(output_path), "%s/profiling_results_%d.csv", data_dir, core_id);
        if (path_len >= sizeof(output_path) || path_len < 0) {
            fprintf(stderr, "Path too long or encoding error: %s/profiling_results_%d.csv\n", data_dir, core_id);
            error_occurred = 1;
            continue;
        }
        
        printf("Processing file: %s -> %s\n", input_path, output_path);
        
        int result = process_file(input_path, output_path, chunk_size);
        if (result == 0) {
            processed_files++;
        } else {
            error_occurred = 1;
        }
    }
    
    closedir(dir);
    
    if (total_files == 0) {
        fprintf(stderr, "No profile data files found in '%s'\n", data_dir);
        return EXIT_FAILURE;
    }
    
    printf("\nProcessing complete:\n");
    printf("- Total files found: %d\n", total_files);
    printf("- Successfully processed: %d\n", processed_files);
    printf("- Failed: %d\n", total_files - processed_files);
    
    return error_occurred ? EXIT_FAILURE : EXIT_SUCCESS;
}