import time
import inspect
from functools import wraps

from .monitoring.health import run_health_check


def health(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")

        start_time = time.perf_counter()

        if inspect.iscoroutinefunction(func):
            response = await func(*args, **kwargs)
        else:
            response = func(*args, **kwargs)

        end_time = time.perf_counter()

        duration = end_time - start_time

        await run_health_check(func_name=func.__name__, request=request, duration=duration)

        return response

    return wrapper
