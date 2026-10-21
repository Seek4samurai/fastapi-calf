import asyncio
import http.client
import json

from .config import config


def emit_event(event: dict):
    connection = None
    try:
        wire_event = {
            **event,
            "_calf_server": config.server,
        }
        payload = json.dumps(wire_event).encode("utf-8")
        connection = http.client.HTTPConnection(
            config.host, config.port, timeout=0.1
        )
        connection.request(
            "POST",
            "/api/events",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        response.read()

    except (ConnectionRefusedError, TimeoutError, OSError, http.client.HTTPException):
        # Monitoring should NEVER crash the API
        pass
    finally:
        if connection is not None:
            connection.close()


async def emit_event_async(event: dict):
    """Send an event without blocking the application's event loop."""
    await asyncio.to_thread(emit_event, event)
