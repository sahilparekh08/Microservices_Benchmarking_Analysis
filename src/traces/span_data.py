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
        self.non_idle_intervals = []

    def get_non_idle_execution_time(self) -> int:
        if self.__non_idle_execution_time is not None:
            return self.__non_idle_execution_time

        if len(self.children) == 0:
            self.non_idle_intervals.append((self.start_time, self.end_time))
            return self.duration
        
        self.children.sort(key=lambda x: x.start_time)

        merged_children_duration = []
        end_time_for_merging = self.children[0].end_time
        duration_for_merging = self.children[0].duration

        # max duration considered for merged interval and not the whole merged interval
        # trying to replicate what jaeger itself does
        
        children_start_end_times_to_consider = []
        child_start_time = self.children[0].start_time
        child_end_time = self.children[0].end_time

        for child in self.children[1:]:
            if child.start_time < end_time_for_merging:
                end_time_for_merging = max(end_time_for_merging, child.end_time)
                if child.duration > duration_for_merging:
                    duration_for_merging = child.duration
                    child_start_time = child.start_time
                    child_end_time = child.end_time
            else:
                merged_children_duration.append(duration_for_merging)
                children_start_end_times_to_consider.append((child_start_time, child_end_time))
                end_time_for_merging = child.end_time
                duration_for_merging = child.duration
                child_start_time = child.start_time
                child_end_time = child.end_time
        merged_children_duration.append(duration_for_merging)
        children_start_end_times_to_consider.append((child_start_time, child_end_time))

        non_idle_execution_time = self.duration
        for duration_for_merging in merged_children_duration:
            non_idle_execution_time -= duration_for_merging
        self.__non_idle_execution_time = non_idle_execution_time

        start_time = self.start_time
        end_time = self.end_time
        for child_start_time, child_end_time in children_start_end_times_to_consider:
            if start_time < child_start_time:
                self.non_idle_intervals.append((start_time, child_start_time))
            start_time = child_end_time
        self.non_idle_intervals.append((start_time, end_time))

        return non_idle_execution_time

    def add_child(self, child: "SpanData"):
        self.children.append(child)

    def __repr__(self):
        non_idle_execution_time = self.get_non_idle_execution_time()
        childrenSpanIds = [child.span_id for child in self.children]

        return f"SpanData(trace_id={self.trace_id}, " \
            f"span_id={self.span_id}, " \
            f"service={self.service}, " \
            f"operation={self.operation}, " \
            f"start_time={self.start_time}, "\
            f"end_time={self.end_time}, " \
            f"duration={self.duration}, " \
            f"non_idle_execution_time={non_idle_execution_time}, " \
            f"non_idle_intervals={self.non_idle_intervals}, " \
            f"children_span_ids={childrenSpanIds})"
