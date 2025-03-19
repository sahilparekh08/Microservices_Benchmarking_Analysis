"""
Trace analysis package.
This package provides functionality for collecting, processing, and analyzing Jaeger traces.
"""

from .data_models import SpanData
from .data_collection import get_trace_ids, get_services, parse_and_save_traces
from .data_processing import process_traces
from .visualization import plot_jaeger_service_data

__all__ = [
    'SpanData',
    'get_trace_ids',
    'get_services',
    'parse_and_save_traces',
    'process_traces',
    'plot_jaeger_service_data'
] 