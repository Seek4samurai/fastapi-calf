import psutil

def cleanup_workers(workers):
    dead_pids = []

    for pid in workers:
        if not psutil.pid_exists(pid):
            dead_pids.append(pid)

    for pid in dead_pids:
        workers.pop(pid, None)
