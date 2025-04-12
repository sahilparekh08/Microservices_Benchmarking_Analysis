#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <immintrin.h>
#include <pqos.h>

// Function to flush a memory range, cache line by cache line
void flush_memory_range(void *addr, size_t size) {
    unsigned char *ptr = (unsigned char *)addr;
    unsigned char *end = ptr + size;
    for (; ptr < end; ptr += 64) {
        _mm_clflush(ptr);
    }
    _mm_mfence(); // Ensure all cache flushes are complete
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: %s <partition_id>\n", argv[0]);
        return 1;
    }
    
    int partition_id = atoi(argv[1]);
    const struct pqos_cap *p_cap;
    const struct pqos_cpuinfo *p_cpu;
    struct pqos_config config;
    int ret;
    
    memset(&config, 0, sizeof(config));
    config.fd_log =  fileno(stdout);
    config.verbose = 0;
    
    ret = pqos_init(&config);
    if (ret != PQOS_RETVAL_OK) {
        printf("Error initializing PQoS library: %d\n", ret);
        return 1;
    }
    
    ret = pqos_cap_get(&p_cap, &p_cpu);
    if (ret != PQOS_RETVAL_OK) {
        printf("Error retrieving PQoS capabilities: %d\n", ret);
        pqos_fini();
        return 1;
    }
    
    const struct pqos_capability *l3ca_cap = NULL;
    ret = pqos_cap_get_type(p_cap, PQOS_CAP_TYPE_L3CA, &l3ca_cap);
    if (ret != PQOS_RETVAL_OK || l3ca_cap == NULL) {
        printf("L3 CAT capability not supported!\n");
        pqos_fini();
        return 1;
    }
    
    unsigned l3_size = p_cpu->l3.total_size;
    printf("Detected L3 cache size: %u KB\n", l3_size/1024);
    
    char *buffer = malloc(l3_size);
    if (!buffer) {
        printf("Memory allocation failed\n");
        pqos_fini();
        return 1;
    }
    
    memset(buffer, 0xFF, l3_size);
    
    unsigned socket_ids[16] = {0};
    unsigned socket_count = 0;
    
    for (unsigned i = 0; i < p_cpu->num_cores; i++) {
        unsigned socket_id = p_cpu->cores[i].socket;
        unsigned j;
        for (j = 0; j < socket_count; j++) {
            if (socket_ids[j] == socket_id)
                break;
        }
        if (j == socket_count && socket_count < 16) {
            socket_ids[socket_count++] = socket_id;
        }
    }
    
    printf("Found %u sockets\n", socket_count);
    
    for (unsigned s = 0; s < socket_count; s++) {
        unsigned socket_id = socket_ids[s];
        struct pqos_l3ca l3ca[4];
        unsigned l3ca_num = 0;
        
        ret = pqos_l3ca_get(socket_id, 4, &l3ca_num, l3ca);
        if (ret != PQOS_RETVAL_OK) {
            printf("Error retrieving L3 CAT config for socket %u: %d\n", socket_id, ret);
            continue;
        }
        
        if (partition_id < l3ca_num) {
            printf("Clearing partition %d (COS: %u) on socket %u with mask: 0x%llx\n", 
                   partition_id, l3ca[partition_id].class_id, socket_id, 
                   (unsigned long long)l3ca[partition_id].u.ways_mask);
            
            flush_memory_range(buffer, l3_size);
        } else {
            printf("Partition ID %d out of range (max: %u) on socket %u\n", 
                   partition_id, l3ca_num-1, socket_id);
        }
    }
    
    free(buffer);
    pqos_fini();
    printf("Cache clearing completed\n");
    return 0;
}