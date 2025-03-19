"""
Profile with traces analysis package.
This package provides functionality to analyze and visualize performance profiles with trace data.
"""

from .main import main
from .constants import DEFAULT_SERVICE_NAME
from .data_loader import load_traces_data, load_perf_data
from .trace_processor import get_non_overlapping_longest_durations, get_highest_resource_usage_traces
from .plotting import (
    plot_aligned_median_resource_usage,
    plot_traces_start_end_times_and_perf_data,
    plot_profile_with_traces
)

__all__ = [
    'main',
    'DEFAULT_SERVICE_NAME',
    'load_traces_data',
    'load_perf_data',
    'get_non_overlapping_longest_durations',
    'get_highest_resource_usage_traces',
    'plot_aligned_median_resource_usage',
    'plot_traces_start_end_times_and_perf_data',
    'plot_profile_with_traces'
] 