import time
from collections import deque

from ..history.history import request_times


recent_latencies = []


def record_request(latency_ms):
    request_times.append(time.time())
    recent_latencies.append(latency_ms)


def get_rps():
    now = time.time()

    while request_times and request_times[0] < now - 1:
        request_times.popleft()

    return len(request_times)


def get_window_latency():
    if not recent_latencies:
        return 0.0

    avg = sum(recent_latencies) / len(recent_latencies)

    recent_latencies.clear()

    return avg
