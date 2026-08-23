import os
from .config import config
from .emitter import emit_event

class Calf:
    @staticmethod
    def listen(port: int, host: str = "127.0.0.1"):
        config.host = host
        config.port = port

        emit_event({
            "type": "process_info",
            "pid": os.getpid(),
        })

        cuda_devices = os.getenv("CUDA_VISIBLE_DEVICES")

        if cuda_devices is not None:
            print(f"CUDA_VISIBLE_DEVICES={cuda_devices}")
        else:
            print("CUDA_VISIBLE_DEVICES is not set")

#
#    BUG: Running daemon after running the server doesn't passes the pid
#
