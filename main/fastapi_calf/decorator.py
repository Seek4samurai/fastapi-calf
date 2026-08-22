import inspect
import time

from datetime import datetime, timezone
from functools import wraps
from fastapi import Request

from .emitter import emit_event


def lookout(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request | None = kwargs.get("request")

        start_timestamp = datetime.now(timezone.utc)
        start_timer = time.perf_counter()

        status_code = 200
        error = None

        try:
            if inspect.iscoroutinefunction(func):
                response = await func(*args, **kwargs)
            else:
                response = func(*args, **kwargs)
            return response

        except Exception as exc:
            status_code = 500
            error = str(exc)
            raise

        finally:
            end_timer = time.perf_counter()
            latency_ms = (end_timer - start_timer) * 1000

            if request:
                body = await request.body()

                event = {
                    "timestamp": start_timestamp.isoformat(),
                    "function": func.__name__,
                    "method": request.method,
                    "path": request.url.path,
                    "query": dict(request.query_params),
                    "request_size": len(body),
                    "latency_ms": latency_ms,
                    "status": status_code,
                    "error": error,
                }

                emit_event(event)

    return wrapper
