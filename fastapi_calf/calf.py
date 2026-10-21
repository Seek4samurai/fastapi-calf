import asyncio
import os
from .config import config
from .blocking import BlockingDetector
from .emitter import emit_event_async
from .lifecycle import CalfLifecycleMiddleware, install_lifecycle_hooks
from .dashboard import install_dashboard_redirect
from .autostart import ensure_collector


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
        dashboard: bool = True,
        dashboard_path: str = "/calf",
        ignore_paths: tuple[str, ...] | list[str] = (),
        auto_start_collector: bool = True,
    ):
        config.host = host
        config.port = port
        config.server = server

        cuda_devices = os.getenv("CUDA_VISIBLE_DEVICES")

        detector = None
        if detect_blocking:
            detector = BlockingDetector(
                emit_event_async,
                interval=block_check_interval / 1000,
                threshold=block_threshold / 1000,
            )

            @app.on_event("shutdown")
            async def stop_blocking_detector():
                await detector.stop()

        @app.on_event("startup")
        async def start_calf():
            if auto_start_collector:
                await asyncio.to_thread(ensure_collector, host, port)
            await emit_event_async({
                "pid": os.getpid(),
                "cuda_visible_devices": cuda_devices,
            })
            if detector is not None:
                detector.start()

        install_lifecycle_hooks()
        if dashboard:
            install_dashboard_redirect(
                app,
                dashboard_path,
                f"http://{host}:{port}/",
            )
        app.add_middleware(
            CalfLifecycleMiddleware,
            emit=emit_event_async,
            detector=detector,
            cuda_devices=cuda_devices,
            dashboard_path=dashboard_path if dashboard else None,
            ignore_paths=("/favicon.ico", *ignore_paths),
        )
