import json
import socket

from .config import config


def emit_event(event: dict):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.05)

            sock.connect((config.host, config.port))

            payload = json.dumps(event).encode("utf-8") + b"\n"

            sock.sendall(payload)

    except (ConnectionRefusedError, TimeoutError, OSError) as error:
        # Monitoring should NEVER crash the API
        print("Calf emitter error:", error)
        pass
