import logging

from pydantic import BaseModel
from pathlib import Path

class ServerConfig(BaseModel):
    """服务器配置 - 命令行参数"""
    host: str = "127.0.0.1"
    port: int = 6900
    max_threads: int = 32
    log_level: int = logging.INFO
    log_dir: Path = Path("logs")
    debug: bool = False
    temp_dir: Path = Path("data/task_cahce")
    output_dir: str = "output"

# ===== 全局配置 =====
server_config = ServerConfig()
