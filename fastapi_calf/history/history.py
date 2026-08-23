from collections import deque


HISTORY_SIZE = 60

cpu_history = deque(maxlen=HISTORY_SIZE)
latency_history = deque(maxlen=HISTORY_SIZE)
rps_history = deque(maxlen=HISTORY_SIZE)

request_times = deque()
