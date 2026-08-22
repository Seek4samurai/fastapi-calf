import inspect
from functools import wraps

from .monitoring.health import run_health_check


def health(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")

        await run_health_check(func.__name__, request)

        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)

        return func(*args, **kwargs)

    return wrapper
