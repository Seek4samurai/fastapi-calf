from .config import config


class Calf:
    @staticmethod
    def listen(port: int, host: str = "127.0.0.1"):
        config.host = host
        config.port = port
