from __future__ import annotations

import http.client
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def collector_is_running(host: str, port: int, timeout: float = 0.15) -> bool:
    connection = None
    try:
        connection = http.client.HTTPConnection(host, port, timeout=timeout)
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        response.read()
        return response.status == 200
    except (OSError, TimeoutError, http.client.HTTPException):
        return False
    finally:
        if connection is not None:
            connection.close()


def _wait_for_collector(host: str, port: int, timeout: float = 4.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if collector_is_running(host, port):
            return True
        time.sleep(0.05)
    return False


def _spawn_collector(host: str, port: int) -> None:
    command = [
        sys.executable,
        "-m",
        "fastapi_calf.daemon",
        "--host",
        host,
        "--port",
        str(port),
        "--no-terminal",
        "--auto-started",
    ]
    options = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        options["start_new_session"] = True
    subprocess.Popen(command, **options)


def ensure_collector(host: str, port: int) -> bool:
    """Start one local collector when none is already listening."""
    if collector_is_running(host, port):
        return True
    if host not in LOCAL_HOSTS:
        return False

    lock_path = Path(tempfile.gettempdir()) / f"fastapi-calf-{port}.starting"
    owns_lock = False
    try:
        try:
            lock_path.mkdir()
            owns_lock = True
        except FileExistsError:
            # Another Uvicorn worker is starting the collector.
            if _wait_for_collector(host, port):
                return True
            # Recover a lock left behind by a worker that was force-killed.
            try:
                if time.time() - lock_path.stat().st_mtime > 4:
                    lock_path.rmdir()
                    return ensure_collector(host, port)
            except OSError:
                pass
            return False

        if collector_is_running(host, port):
            return True
        _spawn_collector(host, port)
        return _wait_for_collector(host, port)
    finally:
        if owns_lock:
            try:
                lock_path.rmdir()
            except OSError:
                pass
