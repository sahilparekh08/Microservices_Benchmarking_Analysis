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

def get_highest_resource_usage_traces(traces_df: pd.DataFrame, profile_df: pd.DataFrame, num_samples: int) -> pd.DataFrame:
    """Get traces with highest resource usage."""
    # Get non-overlapping spans with largest durations for each trace
    non_overlapping_traces_df = get_non_overlapping_longest_durations(traces_df)
    
    trace_stats = []
    
    min_perf_time = profile_df['Time'].min()
    max_perf_time = profile_df['Time'].max()
    
    for _, row in non_overlapping_traces_df.iterrows():
        trace_id = row['trace_id']
        trace_start = row['start_time']
        trace_end = row['end_time']
        duration = row['duration']

        if trace_end < min_perf_time or trace_start > max_perf_time:
            continue
        if trace_start < min_perf_time or trace_end > max_perf_time:
            continue
        
        trace_perf_data = profile_df[
            (profile_df['Time'] >= trace_start) & 
            (profile_df['Time'] <= trace_end)
        ]
        
        if trace_perf_data.empty:
            continue
        
        non_zero_llc_loads = (trace_perf_data['LLC-loads'] > 0).sum()
        non_zero_llc_misses = (trace_perf_data['LLC-misses'] > 0).sum()
        non_zero_instructions = (trace_perf_data['Instructions'] > 0).sum()
        
        total_resource_usage = non_zero_llc_loads + non_zero_llc_misses + non_zero_instructions
        
        trace_stats.append({
            'trace_id': trace_id,
            'start_time': trace_start,
            'end_time': trace_end,
            'non_zero_llc_loads': non_zero_llc_loads,
            'non_zero_llc_misses': non_zero_llc_misses,
            'non_zero_instructions': non_zero_instructions,
            'total_resource_usage': total_resource_usage,
            'duration': duration
        })
    
    trace_stats_df = pd.DataFrame(trace_stats)
    if trace_stats_df.empty:
        return pd.DataFrame()
    
    trace_stats_df = trace_stats_df.sort_values(by='total_resource_usage', ascending=False)
    
    top_traces = trace_stats_df.head(num_samples)
    
    print(f"Top {len(top_traces)} traces by resource usage:")
    for i, (_, row) in enumerate(top_traces.iterrows()):
        print(f"  {i+1}. Trace ID: {row['trace_id']}, "
              f"Non-zero LLC loads: {row['non_zero_llc_loads']}, "
              f"Non-zero LLC misses: {row['non_zero_llc_misses']}, "
              f"Non-zero instructions: {row['non_zero_instructions']}, "
              f"Duration: {row['duration']}, "
              f"Total: {row['total_resource_usage']}")
    
    return top_traces 