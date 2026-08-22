import json
import socket


HOST = "127.0.0.1"
PORT = 8765


def emit_event(event: dict):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.05)

            sock.connect((HOST, PORT))

            payload = json.dumps(event).encode("utf-8") + b"\n"

            sock.sendall(payload)

    except (ConnectionRefusedError, TimeoutError, OSError):
        # Monitoring should NEVER crash the API
        pass
