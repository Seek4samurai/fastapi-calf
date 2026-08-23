import psutil


_processes = {}


def register_process(pid: int):
    if pid in _processes:
        return

    try:
        process = psutil.Process(pid)

        # Prime cpu_percent
        process.cpu_percent(interval=None)

        _processes[pid] = process

    except psutil.NoSuchProcess:
        pass


def get_process_stats(pid: int):
    process = _processes.get(pid)

    if process is None:
        return None

    try:
        return {
            "cpu": process.cpu_percent(interval=None),
            "ram_mb": process.memory_info().rss / 1024 / 1024,
        }

    except psutil.NoSuchProcess:
        _processes.pop(pid, None)
        return None
