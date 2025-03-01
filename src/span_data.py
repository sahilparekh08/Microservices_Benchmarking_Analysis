from typing import List

class SpanData:
    def __init__(self, trace_id: str, span_id: str, service: str, operation: str,
                 start_time: int, duration: int, children: List["SpanData"] = None):
        self.trace_id = trace_id
        self.span_id = span_id
        self.service = service
        self.operation = operation
        self.start_time = start_time
        self.end_time = start_time + duration
        self.duration = duration
        self.children = children if children is not None else []
        self.non_idle_execution_time = self.calculate_non_idle_execution_time()

    def calculate_non_idle_execution_time(self) -> int:
        # Subtract the duration of all child spans from the parent span's duration
        children_duration = sum(child.duration for child in self.children)
        return self.duration - children_duration

    def add_child(self, child: "SpanData"):
        """Add a child span to the list of children."""
        self.children.append(child)
        self.non_idle_execution_time = self.calculate_non_idle_execution_time()  # Recalculate non-idle time

    def __repr__(self):
        return f"SpanData(trace_id={self.trace_id}, span_id={self.span_id}, service={self.service}, " \
               f"operation={self.operation}, start_time={self.start_time}, end_time={self.end_time}, " \
               f"duration={self.duration}, non_idle_execution_time={self.non_idle_execution_time}, " \
               f"children_count={len(self.children)})"
