import os
import time

from .config import config
from .emitter import emit_event


class Calf:
    @staticmethod
    def listen(app, port: int, host: str = "127.0.0.1"):
        config.host = host
        config.port = port

        cuda_devices = os.getenv("CUDA_VISIBLE_DEVICES")

        emit_event({
            "pid": os.getpid(),
            "cuda_visible_devices": cuda_devices,
        })

        @app.middleware("http")
        async def calf_middleware(request, call_next):
            start = time.perf_counter()

            status = 500 # defaults to failure

            try:
                response = await call_next(request)

                status = response.status_code

                return response

            finally:
                latency_ms = (time.perf_counter() - start) * 1000

                emit_event({
                    "pid": os.getpid(),
                    "cuda_visible_devices": cuda_devices,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "latency_ms": latency_ms,
                    "last_called": time.time(),
                })
