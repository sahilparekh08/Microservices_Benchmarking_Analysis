"""
Jaeger trace data collection module.
"""

from .traces_handler import get_trace_ids, get_services, parse_and_save_traces

__all__ = ['get_trace_ids', 'get_services', 'parse_and_save_traces'] 