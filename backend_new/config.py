import logging

from pydantic import BaseModel, Field
from pathlib import Path

class ServerConfig(BaseModel):
    """服务器配置 - 命令行参数"""
    host: str = '127.0.0.1'
    port: int = 6900
    max_threads: int = 32
    log_level: int = logging.INFO
    log_dir: Path = Path('data/logs')
    debug: bool = False
    temp_dir: Path = Path('data/task_cahce')
    output_dir: Path = Path('output')
    segments_dir: Path = Field(default=Path('segments'), exclude=True)

# ===== 全局配置 =====
server = ServerConfig()


def update_server(args: dict):
    global server

    server = ServerConfig.model_validate(args)

