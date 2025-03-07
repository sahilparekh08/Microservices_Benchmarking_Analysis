from typing import List

class SpanData:
    def __init__(self, trace_id: str, span_id: str, service: str, operation: str, start_time: int, duration: int):
        self.trace_id = trace_id
        self.span_id = span_id
        self.service = service
        self.operation = operation
        self.start_time = start_time
        self.end_time = start_time + duration
        self.duration = duration
        self.children = []
        self.__non_idle_execution_time = None

    def get_non_idle_execution_time(self) -> int:
        if self.__non_idle_execution_time is not None:
            return self.__non_idle_execution_time

        if len(self.children) == 0:
            return self.duration
        
        self.children.sort(key=lambda x: x.start_time)

        merged_children = []
        start_time = self.children[0].start_time
        end_time = self.children[0].end_time
        duration = self.children[0].duration

        # max duration considered for merged interval and not the whole merged interval
        # trying to replicate what jaeger traces do

        # TODO: also add a list of start and end non-idle exec times for each child span
        
        for child in self.children[1:]:
            if child.start_time < end_time:
                end_time = max(end_time, child.end_time)
                duration = max(duration, child.duration)
            else:
                merged_children.append((start_time, end_time, duration))
                start_time = child.start_time
                end_time = child.end_time
                duration = child.duration
        merged_children.append((start_time, end_time, duration))

        non_idle_execution_time = self.duration
        for start_time, end_time, duration in merged_children:
            non_idle_execution_time -= duration

        self.__non_idle_execution_time = non_idle_execution_time
        return non_idle_execution_time

    def add_child(self, child: "SpanData"):
        self.children.append(child)

    def __repr__(self):
        non_idle_execution_time = self.get_non_idle_execution_time()

        childrenSpanIds = [child.span_id for child in self.children]
        return f"SpanData(trace_id={self.trace_id}, span_id={self.span_id}, service={self.service}, " \
               f"operation={self.operation}, start_time={self.start_time}, end_time={self.end_time}, " \
               f"duration={self.duration}, non_idle_execution_time={non_idle_execution_time}, " \
               f"children_span_ids={childrenSpanIds})"
