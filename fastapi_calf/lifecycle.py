from __future__ import annotations

import contextvars
from fnmatch import fnmatchcase
import os
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable

from starlette.background import BackgroundTask, BackgroundTasks
from starlette.requests import Request

PHASES = (
    "parsing",
    "dependencies",
    "endpoint",
    "serialization",
    "background",
)


@dataclass
class LifecycleTrace:
    started_at: float = field(default_factory=time.perf_counter)
    phases: dict[str, float] = field(
        default_factory=lambda: {phase: 0.0 for phase in PHASES}
    )
    phase_stack: list[str] = field(default_factory=list)
    last_transition: float = field(default_factory=time.perf_counter)

    def _accrue_current_phase(self, now: float) -> None:
        if self.phase_stack:
            self.phases[self.phase_stack[-1]] += now - self.last_transition
        self.last_transition = now

    async def measure(
        self,
        phase: str,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        self._accrue_current_phase(time.perf_counter())
        self.phase_stack.append(phase)
        try:
            return await operation()
        finally:
            self._accrue_current_phase(time.perf_counter())
            self.phase_stack.pop()

    def finish(self) -> dict[str, float]:
        now = time.perf_counter()
        self._accrue_current_phase(now)
        total = now - self.started_at
        measured = sum(self.phases.values())
        lifecycle = {
            phase: round(seconds * 1000, 3)
            for phase, seconds in self.phases.items()
        }
        # Routing, middleware before/after call_next, response construction,
        # and response transport are represented by the residual.
        lifecycle["middleware"] = round(max(0.0, total - measured) * 1000, 3)
        lifecycle["total"] = round(total * 1000, 3)
        return lifecycle


_current_trace: contextvars.ContextVar[LifecycleTrace | None] = (
    contextvars.ContextVar("fastapi_calf_lifecycle_trace", default=None)
)
_hooks_installed = False


async def _measure_current(
    phase: str,
    operation: Callable[[], Awaitable[Any]],
) -> Any:
    trace = _current_trace.get()
    if trace is None:
        return await operation()
    return await trace.measure(phase, operation)


def install_lifecycle_hooks() -> None:
    """Install concurrency-safe timing hooks once per Python process."""
    global _hooks_installed
    if _hooks_installed:
        return

    import fastapi.routing as fastapi_routing

    original_solve_dependencies = fastapi_routing.solve_dependencies
    original_run_endpoint = fastapi_routing.run_endpoint_function
    original_serialize_response = fastapi_routing.serialize_response
    original_body = Request.body
    original_json = Request.json
    original_get_form = Request._get_form
    original_background_task = BackgroundTask.__call__
    original_background_tasks = BackgroundTasks.__call__

    @wraps(original_solve_dependencies)
    async def solve_dependencies(*args, **kwargs):
        return await _measure_current(
            "dependencies",
            lambda: original_solve_dependencies(*args, **kwargs),
        )

    @wraps(original_run_endpoint)
    async def run_endpoint_function(*args, **kwargs):
        return await _measure_current(
            "endpoint",
            lambda: original_run_endpoint(*args, **kwargs),
        )

    @wraps(original_serialize_response)
    async def serialize_response(*args, **kwargs):
        return await _measure_current(
            "serialization",
            lambda: original_serialize_response(*args, **kwargs),
        )

    @wraps(original_body)
    async def request_body(self, *args, **kwargs):
        return await _measure_current(
            "parsing", lambda: original_body(self, *args, **kwargs)
        )

    @wraps(original_json)
    async def request_json(self, *args, **kwargs):
        return await _measure_current(
            "parsing", lambda: original_json(self, *args, **kwargs)
        )

    @wraps(original_get_form)
    async def request_get_form(self, *args, **kwargs):
        return await _measure_current(
            "parsing", lambda: original_get_form(self, *args, **kwargs)
        )

    @wraps(original_background_task)
    async def background_task(self, *args, **kwargs):
        return await _measure_current(
            "background", lambda: original_background_task(self, *args, **kwargs)
        )

    @wraps(original_background_tasks)
    async def background_tasks(self, *args, **kwargs):
        return await _measure_current(
            "background", lambda: original_background_tasks(self, *args, **kwargs)
        )

    fastapi_routing.solve_dependencies = solve_dependencies
    fastapi_routing.run_endpoint_function = run_endpoint_function
    fastapi_routing.serialize_response = serialize_response
    Request.body = request_body
    Request.json = request_json
    Request._get_form = request_get_form
    BackgroundTask.__call__ = background_task
    BackgroundTasks.__call__ = background_tasks
    _hooks_installed = True


class CalfLifecycleMiddleware:
    def __init__(
        self,
        app,
        *,
        emit,
        detector=None,
        cuda_devices=None,
        dashboard_path=None,
        ignore_paths=(),
    ) -> None:
        self.app = app
        self.emit = emit
        self.detector = detector
        self.cuda_devices = cuda_devices
        self.dashboard_path = (
            "/" + dashboard_path.strip("/") if dashboard_path else None
        )
        self.ignore_paths = tuple(ignore_paths)

    def _should_ignore(self, path: str) -> bool:
        if self.dashboard_path and (
            path == self.dashboard_path
            or path.startswith(self.dashboard_path + "/")
        ):
            return True
        return any(fnmatchcase(path, pattern) for pattern in self.ignore_paths)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self._should_ignore(path):
            await self.app(scope, receive, send)
            return

        trace = LifecycleTrace()
        token = _current_trace.set(trace)
        method = scope.get("method", "")
        status = 500
        request_id = None

        if self.detector is not None:
            request_id = self.detector.register(method, path)

        async def capture_status(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            if self.detector is not None and request_id is not None:
                self.detector.unregister(request_id)

            lifecycle = trace.finish()
            _current_trace.reset(token)
            await self.emit({
                "pid": os.getpid(),
                "cuda_visible_devices": self.cuda_devices,
                "method": method,
                "path": path,
                "status": status,
                "latency_ms": lifecycle["total"],
                "lifecycle": lifecycle,
                "last_called": time.time(),
            })
