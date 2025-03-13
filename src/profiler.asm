section .data
fmt_str: db "%llu, %llu, %llu, %llu", 10, 0 ; Format: Timestamp, LLC Loads, LLC Misses, Instructions
error_msg: db "Failed to set up performance counters.", 10, 0
error_len: equ $ - error_msg

section .bss
fd: resq 1
buf: resb 64
perf_attr: resb 128           ; perf_event_attr structure (single reusable)
counter_fds: resq 3           ; Space for 3 file descriptors (8 bytes each)
pmc_values: resq 3            ; Space to store PMC values
core_number: resq 1
run_seconds: resq 1
cpu_mask: resq 1
filename: resb 256            ; Space for the output file path

section .text
global _start

_start:
    ; Parse command-line arguments
    pop rcx                   ; Get argc
    cmp rcx, 4                ; Check if we have enough arguments
    jl exit_error             ; Exit if not enough arguments
    
    pop rdi                   ; Skip argv[0] (program name)
    
    ; Get core number (argv[1])
    pop rdi                     
    call str_to_int
    mov [core_number], rax
    
    ; Get run seconds (argv[2])
    pop rdi
    call str_to_int
    mov [run_seconds], rax
    
    ; Get filename (argv[3])
    pop rdi
    call copy_filename
    
    ; Set CPU affinity
    mov rax, 1
    mov rcx, [core_number]
    shl rax, cl               ; 1 << core_number
    mov [cpu_mask], rax
    
    mov rax, 10               ; syscall: sched_setaffinity
    mov rdi, 0                ; pid: 0 (self)
    mov rsi, 8                ; size: 8 bytes for CPU mask
    lea rdx, [cpu_mask]       ; mask pointer
    syscall
    
    ; Setup performance counters
    call setup_pmc
    test rax, rax
    jnz pmc_setup_failed
    
    ; Open log file
    mov rax, 2                ; syscall: open
    lea rdi, [filename]       ; filename
    mov rsi, 1089             ; O_WRONLY | O_CREAT | O_APPEND
    mov rdx, 0644             ; file permissions
    syscall
    
    test rax, rax             ; Check for error
    js exit_error
    
    mov [fd], rax             ; Save file descriptor
    
    ; Calculate iterations (run_seconds * 1000)
    mov rax, [run_seconds]
    mov rbx, 1000
    mul rbx
    mov r15, rax              ; Store iteration count in r15
    
loop_start:
    ; Get timestamp
    mov rax, 96               ; syscall: gettimeofday
    lea rdi, [buf]            ; struct timeval
    xor rsi, rsi              ; struct timezone (NULL)
    syscall
    
    ; Read performance counters
    call read_pmc
    
    ; Write results to file
    mov rdi, [fd]             ; file descriptor
    lea rsi, [buf]            ; buffer to write from
    
    ; Format: timestamp, and PMC values
    mov r10, [buf]            ; timestamp
    mov r11, [pmc_values]     ; PMC value 1
    mov r12, [pmc_values+8]   ; PMC value 2
    mov r13, [pmc_values+16]  ; PMC value 3
    
    mov [buf+8], r11          ; PMC 1
    mov [buf+16], r12         ; PMC 2
    mov [buf+24], r13         ; PMC 3
    
    mov rax, 1                ; syscall: write
    mov rdx, 32               ; 4 values, 8 bytes each = 32 bytes
    syscall
    
    ; Small delay (nanosleep)
    mov rax, 35               ; syscall: nanosleep
    lea rdi, [buf]            ; reuse buf for timespec
    mov qword [rdi], 0        ; seconds = 0
    mov qword [rdi+8], 10000  ; nanoseconds = 10000 (10μs)
    xor rsi, rsi              ; second timespec (NULL)
    syscall
    
    ; Decrement counter and loop
    dec r15
    jnz loop_start
    
    ; Close performance counter file descriptors
    mov rcx, 3                ; 3 file descriptors to close
    xor rbx, rbx              ; index
.close_loop:
    mov rdi, [counter_fds+rbx*8]
    
    mov rax, 3                ; syscall: close
    syscall
    
    inc rbx
    loop .close_loop
    
    ; Close log file
    mov rax, 3                ; syscall: close
    mov rdi, [fd]             ; file descriptor
    syscall
    
    ; Exit successfully
    mov rax, 60               ; syscall: exit
    xor rdi, rdi              ; status = 0
    syscall

pmc_setup_failed:
    ; Write error message to stderr
    mov rax, 1                ; syscall: write
    mov rdi, 2                ; file descriptor (stderr)
    lea rsi, [error_msg]      ; error message
    mov rdx, error_len        ; message length
    syscall
    
    ; Exit with error
    mov rax, 60               ; syscall: exit
    mov rdi, 1                ; status = 1
    syscall

; Function to set up performance counters - optimized for Intel Xeon E5 v3
setup_pmc:
    ; Initialize counter fds
    mov qword [counter_fds], 0
    mov qword [counter_fds+8], 0
    mov qword [counter_fds+16], 0
    
    ; First try PERF_TYPE_HARDWARE events (more likely to work on different systems)
    
    ; Setup for LLC references (cache-references)
    lea rdi, [perf_attr]
    call clear_perf_attr
    
    mov dword [perf_attr], 0         ; type = PERF_TYPE_HARDWARE
    mov dword [perf_attr+4], 112     ; size = 112 (PERF_ATTR_SIZE_VER5)
    mov qword [perf_attr+8], 2       ; config = PERF_COUNT_HW_CACHE_REFERENCES
    
    ; Set required flags
    mov dword [perf_attr+16], (1 << 0) | (1 << 1) | (1 << 2)
                                      ; disabled=1, exclude_kernel=1, exclude_hv=1
    
    ; Call perf_event_open
    mov rax, 298                      ; syscall: perf_event_open
    lea rdi, [perf_attr]              ; attr structure
    mov rsi, -1                       ; pid = -1 (current thread/CPU)
    mov rdx, [core_number]            ; cpu 
    mov r10, -1                       ; group_fd = -1 (no group)
    mov r8, 0                         ; flags = 0
    syscall
    
    ; Check for error - if failed, try RAW events
    test rax, rax
    js .try_raw_events
    
    ; Store the fd
    mov [counter_fds], rax
    
    ; Setup for LLC misses (cache-misses)
    lea rdi, [perf_attr]
    call clear_perf_attr
    
    mov dword [perf_attr], 0          ; type = PERF_TYPE_HARDWARE
    mov dword [perf_attr+4], 112      ; size = 112
    mov qword [perf_attr+8], 3        ; config = PERF_COUNT_HW_CACHE_MISSES
    mov dword [perf_attr+16], (1 << 0) | (1 << 1) | (1 << 2)
                                       ; disabled=1, exclude_kernel=1, exclude_hv=1
    
    mov rax, 298                       ; syscall: perf_event_open
    lea rdi, [perf_attr]               ; attr structure
    mov rsi, -1                        ; pid
    mov rdx, [core_number]             ; cpu
    mov r10, -1                        ; group_fd
    mov r8, 0                          ; flags
    syscall
    
    test rax, rax
    js .cleanup_and_error
    
    mov [counter_fds+8], rax
    
    ; Setup for Instructions Retired
    lea rdi, [perf_attr]
    call clear_perf_attr
    
    mov dword [perf_attr], 0           ; type = PERF_TYPE_HARDWARE
    mov dword [perf_attr+4], 112       ; size = 112
    mov qword [perf_attr+8], 1         ; config = PERF_COUNT_HW_INSTRUCTIONS
    mov dword [perf_attr+16], (1 << 0) | (1 << 1) | (1 << 2)
                                        ; disabled=1, exclude_kernel=1, exclude_hv=1
    
    mov rax, 298                        ; syscall: perf_event_open
    lea rdi, [perf_attr]                ; attr structure
    mov rsi, -1                         ; pid
    mov rdx, [core_number]              ; cpu
    mov r10, -1                         ; group_fd
    mov r8, 0                           ; flags
    syscall
    
    test rax, rax
    js .cleanup_and_error
    
    mov [counter_fds+16], rax
    
    ; Enable all counters
    call enable_counters
    
    xor rax, rax                        ; return success
    ret

.try_raw_events:
    ; Try with RAW events for LLC references - event=0x2e, umask=0x4f for Intel
    lea rdi, [perf_attr]
    call clear_perf_attr
    
    mov dword [perf_attr], 4            ; type = PERF_TYPE_RAW
    mov dword [perf_attr+4], 112        ; size = 112 (PERF_ATTR_SIZE_VER5)
    mov qword [perf_attr+8], 0x4F2E     ; config = (umask << 8) | event
    
    ; Set required flags
    mov dword [perf_attr+16], (1 << 0) | (1 << 1) | (1 << 2)
                                         ; disabled=1, exclude_kernel=1, exclude_hv=1
    
    ; Call perf_event_open
    mov rax, 298                         ; syscall: perf_event_open
    lea rdi, [perf_attr]                 ; attr structure
    mov rsi, -1                          ; pid = -1 (current thread/CPU)
    mov rdx, [core_number]               ; cpu 
    mov r10, -1                          ; group_fd = -1 (no group)
    mov r8, 0                            ; flags = 0
    syscall
    
    ; Check for error - if failed, return error
    test rax, rax
    js .cleanup_and_error
    
    ; Store the fd
    mov [counter_fds], rax
    
    ; Setup for cache-misses - event=0x2e, umask=0x41 for Intel
    lea rdi, [perf_attr]
    call clear_perf_attr
    
    mov dword [perf_attr], 4             ; type = PERF_TYPE_RAW
    mov dword [perf_attr+4], 112         ; size = 112
    mov qword [perf_attr+8], 0x412E      ; config = (umask << 8) | event
    mov dword [perf_attr+16], (1 << 0) | (1 << 1) | (1 << 2)
                                          ; disabled=1, exclude_kernel=1, exclude_hv=1
    
    mov rax, 298                          ; syscall: perf_event_open
    lea rdi, [perf_attr]                  ; attr structure
    mov rsi, -1                           ; pid
    mov rdx, [core_number]                ; cpu
    mov r10, -1                           ; group_fd
    mov r8, 0                             ; flags
    syscall
    
    test rax, rax
    js .cleanup_and_error
    
    mov [counter_fds+8], rax
    
    ; Setup for Instructions Retired counter (event 0xC0) for Intel
    lea rdi, [perf_attr]
    call clear_perf_attr
    
    mov dword [perf_attr], 4              ; type = PERF_TYPE_RAW
    mov dword [perf_attr+4], 112          ; size = 112
    mov qword [perf_attr+8], 0xC0         ; config = Instructions retired (0xC0)
    mov dword [perf_attr+16], (1 << 0) | (1 << 1) | (1 << 2)
                                           ; disabled=1, exclude_kernel=1, exclude_hv=1
    
    mov rax, 298                           ; syscall: perf_event_open
    lea rdi, [perf_attr]                   ; attr structure
    mov rsi, -1                            ; pid
    mov rdx, [core_number]                 ; cpu
    mov r10, -1                            ; group_fd
    mov r8, 0                              ; flags
    syscall
    
    test rax, rax
    js .cleanup_and_error
    
    mov [counter_fds+16], rax
    
    ; Enable all counters
    call enable_counters
    
    xor rax, rax                           ; return success
    ret

.cleanup_and_error:
    ; Close any open fds before returning error
    mov rdi, [counter_fds]
    test rdi, rdi
    jle .return_error
    
    mov rax, 3                                ; syscall: close
    syscall
    
    mov rdi, [counter_fds+8]
    test rdi, rdi
    jle .return_error
    
    mov rax, 3                                ; syscall: close
    syscall
    
    mov rdi, [counter_fds+16]
    test rdi, rdi
    jle .return_error
    
    mov rax, 3                                ; syscall: close
    syscall
    
.return_error:
    mov rax, 1                                ; return error
    ret

; Function to enable all counters
enable_counters:
    mov rax, 16                               ; syscall: ioctl
    mov rdi, [counter_fds]                    ; fd
    mov rsi, 0x2400                           ; request: PERF_EVENT_IOC_ENABLE
    xor rdx, rdx                              ; arg
    syscall
    
    mov rax, 16                               ; syscall: ioctl
    mov rdi, [counter_fds+8]                  ; fd
    mov rsi, 0x2400                           ; request: PERF_EVENT_IOC_ENABLE
    xor rdx, rdx                              ; arg
    syscall
    
    mov rax, 16                               ; syscall: ioctl
    mov rdi, [counter_fds+16]                 ; fd
    mov rsi, 0x2400                           ; request: PERF_EVENT_IOC_ENABLE
    xor rdx, rdx                              ; arg
    syscall
    
    ret

; Function to clear perf_attr structure
clear_perf_attr:
    push rcx
    mov rcx, 128/8                            ; 128 bytes / 8 = 16 qwords
    xor rax, rax
    rep stosq
    pop rcx
    ret
    
; Function to read performance counters
read_pmc:
    ; Read from perf_event_open counters using read()
    mov rdi, [counter_fds]
    mov rax, 0                                ; syscall: read
    lea rsi, [pmc_values]                     ; buffer
    mov rdx, 8                                ; size
    syscall
    
    mov rdi, [counter_fds+8]
    mov rax, 0                                ; syscall: read
    lea rsi, [pmc_values+8]                   ; buffer
    mov rdx, 8                                ; size
    syscall
    
    mov rdi, [counter_fds+16]
    mov rax, 0                                ; syscall: read
    lea rsi, [pmc_values+16]                  ; buffer
    mov rdx, 8                                ; size
    syscall
    
    ret

exit_error:
    ; Exit with error
    mov rax, 60                               ; syscall: exit
    mov rdi, 1                                ; status = 1
    syscall
    
; Function: Convert string to integer
str_to_int:
    xor rax, rax                              ; Clear result
.loop:
    movzx rcx, byte [rdi]                     ; Load next character
    test rcx, rcx                             ; Check for null terminator
    jz .done
    sub rcx, '0'                              ; Convert ASCII to integer
    
    ; Check if valid digit (0-9)
    cmp rcx, 0
    jl .done
    cmp rcx, 9
    jg .done
    
    ; Multiply current result by 10 and add new digit
    imul rax, 10
    add rax, rcx
    
    inc rdi                                   ; Move to next char
    jmp .loop
.done:
    ret
    
; Function: Copy output file path to filename buffer
copy_filename:
    lea rsi, [filename]                       ; Destination buffer
.loop:
    mov al, byte [rdi]                        ; Load next char from input path
    test al, al                               ; Check if null terminator
    jz .done_copy
    mov byte [rsi], al                        ; Copy char to filename buffer
    inc rdi
    inc rsi
    jmp .loop
.done_copy:
    mov byte [rsi], 0                         ; Ensure null termination
    ret