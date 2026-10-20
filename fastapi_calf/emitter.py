import json
import socket

from .config import config


def emit_event(event: dict):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.05)

            sock.connect((config.host, config.port))

            wire_event = {
                **event,
                "_calf_server": config.server,
            }
            payload = json.dumps(wire_event).encode("utf-8") + b"\n"

            sock.sendall(payload)

    except (ConnectionRefusedError, TimeoutError, OSError) as error:
        # Monitoring should NEVER crash the API
        print(f"Calf emitter error connecting to {config.host}:{config.port}: {error}")
        pass
