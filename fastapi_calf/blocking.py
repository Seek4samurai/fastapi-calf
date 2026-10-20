from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from typing import Awaitable, Callable


@dataclass
class ActiveRequest:
    request_id: str
    method: str
    path: str
    started_at: float
    task_name: str | None
    ended_at: float | None = None


class BlockingDetector:
    """Detect periods during which an asyncio event loop cannot run.

    Event-loop lag proves that the worker was stalled, but when requests overlap
    it cannot prove which request caused the stall. Events therefore contain all
    requests that overlapped the blocked interval as ``affected_requests``.
    """

    def __init__(
        self,
        emit: Callable[[dict], Awaitable[None]],
        *,
        interval: float = 0.05,
        threshold: float = 0.10,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be greater than zero")
        if threshold <= 0:
            raise ValueError("threshold must be greater than zero")

        self.emit = emit
        self.interval = interval
        self.threshold = threshold
        self.active: dict[str, ActiveRequest] = {}
        self.recently_finished: deque[ActiveRequest] = deque()
        self._task: asyncio.Task | None = None

    def register(self, method: str, path: str) -> str:
        request_id = uuid.uuid4().hex
        task = asyncio.current_task()
        self.active[request_id] = ActiveRequest(
            request_id=request_id,
            method=method,
            path=path,
            started_at=time.perf_counter(),
            task_name=task.get_name() if task else None,
        )
        return request_id

    def unregister(self, request_id: str) -> None:
        request = self.active.pop(request_id, None)
        if request is not None:
            request.ended_at = time.perf_counter()
            self.recently_finished.append(request)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._watch(), name="fastapi-calf-loop-watchdog"
            )

    async def stop(self) -> None:
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def _requests_overlapping(self, blocked_since: float) -> list[dict]:
        while (
            self.recently_finished
            and self.recently_finished[0].ended_at is not None
            and self.recently_finished[0].ended_at < blocked_since
        ):
            self.recently_finished.popleft()

        requests = [
            request
            for request in (*self.active.values(), *self.recently_finished)
            if request.started_at <= time.perf_counter()
            and (request.ended_at is None or request.ended_at >= blocked_since)
        ]
        return [asdict(request) for request in requests]

    async def _watch(self) -> None:
        loop = asyncio.get_running_loop()
        expected = loop.time() + self.interval

        while True:
            await asyncio.sleep(self.interval)
            now = loop.time()
            lag = max(0.0, now - expected)
            blocked_since = time.perf_counter() - lag
            expected = now + self.interval

            if lag < self.threshold:
                self._requests_overlapping(time.perf_counter())
                continue

            await self.emit(
                {
                    "type": "loop_blocked",
                    "pid": os.getpid(),
                    "blocked_ms": lag * 1000,
                    "affected_requests": self._requests_overlapping(blocked_since),
                    "timestamp": time.time(),
                }
            )
            # Event delivery is deliberately outside the measured interval. A
            # slow or unavailable dashboard must not look like application lag.
            expected = loop.time() + self.interval
