import json
import socket
import sqlite3

import psutil

from .config import config
from .storage import save_request_metrics


def emit_event(event: dict):
    persisted = False
    if config.database_path is not None and config.event_table is not None:
        try:
            process = psutil.Process()
            save_request_metrics(
                config.database_path,
                config.event_table,
                event,
                cpu_percent=process.cpu_percent(),
                memory_mb=process.memory_info().rss / (1024 * 1024),
            )
            persisted = True
        except (OSError, sqlite3.Error, psutil.Error) as error:
            # Persistence is best-effort, just like dashboard delivery.
            print("Calf storage error:", error)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.05)

            sock.connect((config.host, config.port))

            wire_event = {
                **event,
                "_calf_server": config.server,
                "_calf_database_path": str(config.database_path),
                "_calf_table": config.event_table,
                "_calf_persisted": persisted,
            }
            payload = json.dumps(wire_event).encode("utf-8") + b"\n"

            sock.sendall(payload)

    except (ConnectionRefusedError, TimeoutError, OSError) as error:
        # Monitoring should NEVER crash the API
        print(f"Calf emitter error connecting to {config.host}:{config.port}: {error}")
        pass
