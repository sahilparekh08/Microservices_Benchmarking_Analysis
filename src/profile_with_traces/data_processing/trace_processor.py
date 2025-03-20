"""
Functions for processing trace data.
"""

import pandas as pd
from typing import Dict, Any, List

def get_non_overlapping_longest_durations(traces_df: pd.DataFrame) -> pd.DataFrame:
    """Get non-overlapping spans with longest durations for each trace."""
    result_rows = []
    
    for trace_id in traces_df['trace_id'].unique():
        trace_data = traces_df[traces_df['trace_id'] == trace_id].copy()
        trace_data = trace_data.sort_values(by='duration', ascending=False)
        
        selected_spans = []
        
        for _, row in trace_data.iterrows():
            start_time = row['start_time']
            end_time = row['end_time']
            
            overlaps = False
            for span_start, span_end in selected_spans:
                if not (end_time <= span_start or start_time >= span_end):
                    overlaps = True
                    break
            
            if not overlaps:
                selected_spans.append((start_time, end_time))
                result_rows.append(row)
    
    if not result_rows:
        return pd.DataFrame()
    
    return pd.DataFrame(result_rows)

def get_highest_resource_usage_traces(traces_df: pd.DataFrame, core_to_perf_data_df: Dict[str, pd.DataFrame], num_samples: int) -> pd.DataFrame:
    """Get traces with highest resource usage."""
    # Get non-overlapping spans with largest durations for each trace
    non_overlapping_traces_df = get_non_overlapping_longest_durations(traces_df)
    
    trace_stats = []
    
    min_perf_time = 0
    max_perf_time = 0
    for _, perf_data_df in core_to_perf_data_df.items():
        min_perf_time = perf_data_df['Time'].min()
        max_perf_time = perf_data_df['Time'].max()
    
    for _, row in non_overlapping_traces_df.iterrows():
        trace_id = row['trace_id']
        trace_start = row['start_time']
        trace_end = row['end_time']
        duration = row['duration']

        if trace_end < min_perf_time or trace_start > max_perf_time:
            continue
        if trace_start < min_perf_time or trace_end > max_perf_time:
            continue

        non_zero_llc_loads = 0
        non_zero_llc_misses = 0
        non_zero_instructions = 0

        curr_core_with_highest_instructions = None
        highest_instructions = 0
        core_to_instructions = {}
        core_to_llc_loads = {}
        core_to_llc_misses = {}

        for core_no, perf_data_df in core_to_perf_data_df.items():
            trace_perf_data = perf_data_df[
                (perf_data_df['Time'] >= trace_start) & 
                (perf_data_df['Time'] <= trace_end)
            ]

            if trace_perf_data.empty:
                continue

            instructions_count = (trace_perf_data['Instructions'] > 0).sum()
            llc_loads_count = (trace_perf_data['LLC-loads'] > 0).sum()
            llc_misses_count = (trace_perf_data['LLC-misses'] > 0).sum()

            core_to_instructions[core_no] = instructions_count
            core_to_llc_loads[core_no] = llc_loads_count
            core_to_llc_misses[core_no] = llc_misses_count

            non_zero_llc_loads += llc_loads_count
            non_zero_llc_misses += llc_misses_count
            non_zero_instructions += instructions_count

            if instructions_count > highest_instructions:
                highest_instructions = instructions_count
                curr_core_with_highest_instructions = core_no
        
        total_resource_usage = non_zero_llc_loads + non_zero_llc_misses + non_zero_instructions
        
        trace_stats.append({
            'trace_id': trace_id,
            'start_time': trace_start,
            'end_time': trace_end,
            'non_zero_llc_loads': non_zero_llc_loads,
            'non_zero_llc_misses': non_zero_llc_misses,
            'non_zero_instructions': non_zero_instructions,
            'total_resource_usage': total_resource_usage,
            'duration': duration,
            'core_with_highest_instructions': curr_core_with_highest_instructions,
            'core_to_instructions': core_to_instructions,
            'core_to_llc_loads': core_to_llc_loads,
            'core_to_llc_misses': core_to_llc_misses
        })
    
    trace_stats_df = pd.DataFrame(trace_stats)
    if trace_stats_df.empty:
        return pd.DataFrame()
    
    trace_stats_df = trace_stats_df.sort_values(by='total_resource_usage', ascending=False)
    
    top_traces = trace_stats_df.head(num_samples)
    
    print(f"Top {len(top_traces)} traces by resource usage:")
    for i, (_, row) in enumerate(top_traces.iterrows()):

        core_to_instructions_str = ""
        for core_no, instructions in row['core_to_instructions'].items():
                core_to_instructions_str += f"{core_no}: {instructions}, "

        core_to_llc_loads_str = ""
        for core_no, llc_loads in row['core_to_llc_loads'].items():
            core_to_llc_loads_str += f"{core_no}: {llc_loads}, "

        core_to_llc_misses_str = ""
        for core_no, llc_misses in row['core_to_llc_misses'].items():
            core_to_llc_misses_str += f"{core_no}: {llc_misses}, "

        print(f"  {i+1}. Trace ID: {row['trace_id']}, "
              f"Non-zero LLC loads: {row['non_zero_llc_loads']}, "
              f"Non-zero LLC misses: {row['non_zero_llc_misses']}, "
              f"Non-zero instructions: {row['non_zero_instructions']}, "
              f"Duration: {row['duration']}, "
              f"Total: {row['total_resource_usage']}, "
              f"Core with highest instructions: {row['core_with_highest_instructions']}, "
              f"Core to instructions: {core_to_instructions_str}, "
              f"Core to LLC loads: {core_to_llc_loads_str}, "
              f"Core to LLC misses: {core_to_llc_misses_str}")
    
    return top_traces 