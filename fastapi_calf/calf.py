import os
import time

from .config import config
from .blocking import BlockingDetector
from .emitter import emit_event, emit_event_async


class Calf:
    @staticmethod
    def listen(
        app,
        port: int,
        server: str,
        host: str = "127.0.0.1",
        *,
        detect_blocking: bool = True,
        block_threshold: float = 100,
        block_check_interval: float = 50,
    ):
        config.host = host
        config.port = port
        config.server = server

        cuda_devices = os.getenv("CUDA_VISIBLE_DEVICES")

        emit_event({
            "pid": os.getpid(),
            "cuda_visible_devices": cuda_devices,
        })

        detector = None
        if detect_blocking:
            detector = BlockingDetector(
                emit_event_async,
                interval=block_check_interval / 1000,
                threshold=block_threshold / 1000,
            )

            @app.on_event("startup")
            async def start_blocking_detector():
                detector.start()

            @app.on_event("shutdown")
            async def stop_blocking_detector():
                await detector.stop()

        @app.middleware("http")
        async def calf_middleware(request, call_next):
            start = time.perf_counter()

            request_id = None
            if detector is not None:
                request_id = detector.register(request.method, request.url.path)

            status = 500 # defaults to failure

            try:
                response = await call_next(request)

                status = response.status_code

                return response

            finally:
                if detector is not None and request_id is not None:
                    detector.unregister(request_id)

                latency_ms = (time.perf_counter() - start) * 1000

                await emit_event_async({
                    "pid": os.getpid(),
                    "cuda_visible_devices": cuda_devices,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "latency_ms": latency_ms,
                    "last_called": time.time(),
                })
