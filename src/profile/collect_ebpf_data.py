#!/usr/bin/env python3

from bcc import BPF
import time
import argparse
import os
import signal
import sys
from typing import Dict, List, Optional, TextIO, Tuple, Union, Any
from ctypes import Structure, c_uint64, c_uint32
import ctypes

# Performance event type constants
PERF_TYPE_HARDWARE: int = 0
PERF_TYPE_SOFTWARE: int = 1
PERF_TYPE_RAW: int = 4
PERF_COUNT_HW_INSTRUCTIONS: int = 1
PERF_COUNT_SW_CPU_CLOCK: int = 0

class Args:
    pid: int
    duration: int
    output: str

class CounterStruct(Structure):
    _fields_: List[Tuple[str, Any]] = [
        ("llc_loads", c_uint64),
        ("llc_misses", c_uint64),
        ("instructions", c_uint64),
        ("timestamp", c_uint64)
    ]

def parse_arguments() -> Args:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='High-frequency LLC and instruction recording with eBPF'
    )
    parser.add_argument('-p', '--pid', type=int, required=True, help='Process ID to monitor')
    parser.add_argument('-d', '--duration', type=int, default=15, help='Duration in seconds (default: 15)')
    parser.add_argument('-o', '--output', type=str, default='high_freq_perf_data.csv', help='Output file')
    return parser.parse_args()

def load_bpf_program(pid: int) -> BPF:
    # BPF program with counters for LLC loads, misses, and instructions
    bpf_text: str = """
    #include <uapi/linux/ptrace.h>
    #include <linux/sched.h>

    // Per-second counters
    struct counter_t {
        u64 llc_loads;
        u64 llc_misses;
        u64 instructions;
        u64 timestamp;
    };

    // BPF maps
    BPF_ARRAY(counters, struct counter_t, 60);  // Up to 60 seconds of data
    BPF_HASH(current_index, u32, u32);

    // Handler for LLC loads
    int on_llc_loads(struct bpf_perf_event_data *ctx) {
        u32 pid = bpf_get_current_pid_tgid() >> 32;
        if (pid != FILTER_PID)
            return 0;
        
        // Get current second index
        u32 zero = 0;
        u32 *index_ptr = current_index.lookup_or_init(&zero, &zero);
        if (!index_ptr || *index_ptr >= 60)
            return 0;
        
        struct counter_t *counter = counters.lookup(index_ptr);
        if (counter) {
            counter->llc_loads++;
            // Update timestamp every time to get the latest
            counter->timestamp = bpf_ktime_get_ns();
        }
        
        return 0;
    }

    // Handler for LLC misses
    int on_llc_misses(struct bpf_perf_event_data *ctx) {
        u32 pid = bpf_get_current_pid_tgid() >> 32;
        if (pid != FILTER_PID)
            return 0;
        
        u32 zero = 0;
        u32 *index_ptr = current_index.lookup_or_init(&zero, &zero);
        if (!index_ptr || *index_ptr >= 60)
            return 0;
        
        struct counter_t *counter = counters.lookup(index_ptr);
        if (counter) {
            counter->llc_misses++;
        }
        
        return 0;
    }

    // Handler for instructions
    int on_instructions(struct bpf_perf_event_data *ctx) {
        u32 pid = bpf_get_current_pid_tgid() >> 32;
        if (pid != FILTER_PID)
            return 0;
        
        u32 zero = 0;
        u32 *index_ptr = current_index.lookup_or_init(&zero, &zero);
        if (!index_ptr || *index_ptr >= 60)
            return 0;
        
        struct counter_t *counter = counters.lookup(index_ptr);
        if (counter) {
            counter->instructions++;
        }
        
        return 0;
    }

    // Timer to advance to next second
    int on_tick(struct bpf_perf_event_data *ctx) {
        u32 zero = 0;
        u32 *index_ptr = current_index.lookup_or_init(&zero, &zero);
        if (!index_ptr || *index_ptr >= 60)
            return 0;
            
        // Increment the index for next second
        (*index_ptr)++;
        
        return 0;
    }
    """

    bpf_text = bpf_text.replace('FILTER_PID', str(pid))
    return BPF(text=bpf_text)

def attach_perf_events(bpf: BPF, pid: int) -> None:
    # Attach to LLC loads
    bpf.attach_perf_event(
        ev_type=PERF_TYPE_RAW, 
        ev_config=0x01D1, 
        fn_name="on_llc_loads",
        sample_period=0, 
        sample_freq=10000, 
        pid=pid
    )

    # Attach to LLC misses
    bpf.attach_perf_event(
        ev_type=PERF_TYPE_RAW, 
        ev_config=0x01D2,
        fn_name="on_llc_misses",
        sample_period=0, 
        sample_freq=10000, 
        pid=pid
    )

    # Attach to instructions
    bpf.attach_perf_event(
        ev_type=PERF_TYPE_HARDWARE, 
        ev_config=PERF_COUNT_HW_INSTRUCTIONS,
        fn_name="on_instructions",
        sample_period=0, 
        sample_freq=10000, 
        pid=pid
    )

    # Attach to CPU clock for ticks
    bpf.attach_perf_event(
        ev_type=PERF_TYPE_SOFTWARE,
        ev_config=PERF_COUNT_SW_CPU_CLOCK,
        fn_name="on_tick",
        sample_period=0, 
        sample_freq=1, 
        pid=-1
    )

class PerformanceMonitor:
    def __init__(self, bpf: BPF, args: Args) -> None:
        self.bpf = bpf
        self.args = args
        self.output_file: TextIO = open(args.output, 'w')
        self.output_file.write("Timestamp,LLC-loads,LLC-misses,Instructions\n")
        self.counters_table = bpf["counters"]
        self.index_table = bpf["current_index"]
        
    def setup_signal_handler(self) -> None:
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, sig: Optional[int], frame: Optional[Any]) -> None:
        print(f"Recording complete. Data saved to {self.args.output}")
        self.output_file.close()
        sys.exit(0)
        
    def run(self) -> None:
        print(f"Recording at 10,000 Hz for PID {self.args.pid} for {self.args.duration} seconds")
        print(f"Data will be saved to {self.args.output}")
        
        start_time: float = time.time()
        expected_end_time: float = start_time + self.args.duration

        try:
            remaining_time = expected_end_time - time.time()
            while remaining_time > 0:
                time.sleep(min(1, remaining_time))
                remaining_time = expected_end_time - time.time()
                
                elapsed = time.time() - start_time
                print(f"\rRecording: {elapsed:.1f}/{self.args.duration} seconds complete...", end="")
                
            print("Recording complete, processing data...")
            self.process_data()
        except KeyboardInterrupt:
            print("Recording interrupted.")
        finally:
            self.signal_handler(None, None)
        
    def process_data(self) -> None:
        key = ctypes.c_uint32(0)
        current_idx_leaf = self.index_table[key]
        current_idx: int = current_idx_leaf.value

        for i in range(current_idx):
            i_key = ctypes.c_uint32(i)
            counter_data = self.counters_table[i_key]
            timestamp: int = counter_data.timestamp
            llc_loads: int = counter_data.llc_loads
            llc_misses: int = counter_data.llc_misses
            instructions: int = counter_data.instructions
            self.output_file.write(f"{timestamp},{llc_loads},{llc_misses},{instructions}\n")

        zeros_idx = self.index_table.Leaf(0)
        self.index_table[key] = zeros_idx
        
        for i in range(60):
            i_key = ctypes.c_uint32(i)
            zeros_counter = self.counters_table.Leaf(0, 0, 0, 0)
            self.counters_table[i_key] = zeros_counter

        self.output_file.flush()

def main() -> None:
    args: Args = parse_arguments()
    bpf: BPF = load_bpf_program(args.pid)
    attach_perf_events(bpf, args.pid)
    
    monitor: PerformanceMonitor = PerformanceMonitor(bpf, args)
    monitor.setup_signal_handler()
    monitor.run()

if __name__ == "__main__":
    main()
    