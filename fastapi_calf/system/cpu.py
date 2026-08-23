import psutil


_process = None


def set_process(pid: int):
    global _process

    _process = psutil.Process(pid)

    # Prime CPU measurement
    _process.cpu_percent(interval=None)


def get_process_stats():
    if _process is None:
        return None

    try:
        return {
            "cpu": _process.cpu_percent(interval=None),
            "ram_mb": _process.memory_info().rss / (1024 * 1024),
        }

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None
