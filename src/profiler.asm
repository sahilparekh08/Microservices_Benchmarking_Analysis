.section .data
    fmt_str:   .asciz "%llu,%llu,%llu,%llu\n"  # Format: Timestamp, LLC Loads, LLC Misses, Instructions

.section .bss
    fd:    .quad 0
    buf:   .skip 64
    core_number: .quad 0
    run_seconds: .quad 0
    cpu_mask:    .quad 0
    filename:  .skip 256        # Space for the output file path

.section .text
.global _start

_start:
    # Read command-line arguments
    mov 16(%rsp), %rdi   # argv[1] (core number)
    call str_to_int
    mov %rax, core_number

    mov 24(%rsp), %rdi   # argv[2] (run seconds)
    call str_to_int
    mov %rax, run_seconds

    mov 32(%rsp), %rdi   # argv[3] (profile data output path)
    call copy_filename   # Copy the third argument to filename

    # Set CPU affinity
    mov $10, %rax        # syscall: sched_setaffinity
    mov $0, %rdi         # pid: 0 (self)
    mov $8, %rsi         # size: 8 bytes for CPU mask
    mov core_number(%rip), %rcx
    mov $1, %rax
    shl %cl, %rax        # cpu_mask = 1 << core_number
    mov %rax, cpu_mask
    lea cpu_mask(%rip), %rdx
    syscall

    # Open log file
    mov $2, %rax
    lea filename(%rip), %rdi
    mov $1089, %rsi      # O_WRONLY | O_CREAT | O_APPEND
    mov $0644, %rdx
    syscall
    mov %rax, fd

    # Convert run_seconds to iterations (run_seconds * 100000)
    mov run_seconds(%rip), %r8
    imul $100000, %r8
    mov %r8, %r9         # Store iteration count

loop:
    # Get current timestamp
    mov $96, %rax
    mov $0, %rdi
    lea buf(%rip), %rsi
    syscall
    movq buf(%rip), %r10

    # Read LLC Loads
    mov $0x2e, %ecx
    rdpmc
    mov %rax, %r11

    # Read LLC Misses
    mov $0x2f, %ecx
    rdpmc
    mov %rax, %r12

    # Read Instructions Retired
    mov $0xc0, %ecx
    rdpmc
    mov %rax, %r13

    # Write results to file
    mov $1, %rax
    mov fd, %rdi
    lea buf(%rip), %rsi
    movq %r10, (%rsi)
    movq %r11, 8(%rsi)
    movq %r12, 16(%rsi)
    movq %r13, 24(%rsi)
    mov $32, %rdx
    syscall

    # Wait 10µs
    mov $35, %rax
    lea buf(%rip), %rdi
    xor %rsi, %rsi
    syscall

    dec %r9
    jnz loop

    # Close file
    mov $3, %rax
    mov fd, %rdi
    syscall

    # Exit
    mov $60, %rax
    xor %rdi, %rdi
    syscall

# Function: Convert string to integer
str_to_int:
    xor %rax, %rax       # Clear result
    xor %rcx, %rcx       # Digit holder
.loop:
    movzb (%rdi), %rcx   # Load next character
    test %rcx, %rcx      # Check for null terminator
    jz .done
    sub $'0', %rcx       # Convert ASCII to integer
    imul $10, %rax       # Multiply current result by 10
    add %rcx, %rax       # Add new digit
    inc %rdi             # Move to next char
    jmp .loop
.done:
    ret

# Function: Copy output file path (argv[3]) to filename buffer
copy_filename:
    lea filename(%rip), %rsi   # Destination buffer
.loop:
    movb (%rdi), %al           # Load next char from input path
    test %al, %al              # Check if null terminator
    jz .done_copy
    movb %al, (%rsi)           # Copy char to filename buffer
    inc %rdi
    inc %rsi
    jmp .loop
.done_copy:
    ret
