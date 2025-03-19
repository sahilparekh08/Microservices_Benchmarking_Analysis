"""
Profile analysis package.
This package provides functionality for collecting, parsing, and analyzing performance data.
"""

from .data_collection import collect_ebpf_data
from .data_processing import parse_perf_data
from .visualization import plot_profile_data

__all__ = [
    'collect_ebpf_data',
    'parse_perf_data',
    'plot_profile_data'
] 