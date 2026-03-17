from pydantic import BaseModel, Field, computed_field
from typing import Optional
from enum import Enum
from pathlib import Path
from datetime import datetime
from hashlib import md5 as hash_func
import logging


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待中
    PARSING = "parsing"           # 解析中
    DOWNLOADING = "downloading"   # 下载中
    MERGING = "merging"           # 合并中
    PAUSED = "paused"             # 已暂停
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


class ServerConfig(BaseModel):
    """服务器配置 - 命令行参数"""
    host: str = "127.0.0.1"
    port: int = 6900
    max_threads: int = 32
    log_level: int = logging.INFO
    log_dir: Path = Path("logs")
    debug: bool = False
    temp_dir: Path = Path("data/temp_segments")
    output_dir: str = "output"

class DownloadArgs(BaseModel):
    """下载任务请求参数"""
    url: str
    threads: Optional[int] = None
    output: Optional[str] = None
    max_rounds: int = 5
    keep_cache: bool = False
    sequential: bool = False

class DownloadResponse(BaseModel):
    """下载任务响应"""
    success: bool
    task_id: str
    status: TaskStatus

class TaskInfo(BaseModel):
    """任务信息"""
    task_id: str
    segments_downloaded: int
    total_segments: int
    output_name: str

class ListTaskResponse(BaseModel):
    """任务列表响应"""
    success: bool
    tasks: list[TaskInfo]
    total_count: int

class MetaData(BaseModel):
    """缓存元数据"""
    url: str

    created_at: datetime = Field(default_factory=datetime.now)
    state: TaskStatus = TaskStatus.PENDING
    slice_files: list[str] = []  # 分片 URL 列表
    downloaded_mask: int = 0
    totol_slice: int = 0
    output_name: str = 'video.mp4'

    def get_base_url(self) -> str:
        """获取 URL 的基准路径"""
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        path = parsed.path

        if "/" in path:
            path = path.rsplit("/", 1)[0] + "/"

        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def extract_query_params(self) -> str:
        """提取 URL 中的查询参数"""
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        if parsed.query:
            return f"?{parsed.query}"
        return ""

    def is_relative_segment_url(self, segment_url: str, base_url: str) -> bool:
        """判断分片 URL 是否是通过相对路径拼接而成的"""
        return segment_url.startswith(base_url)

    def append_query_params(self, url: str, query_params: str) -> str:
        """给 URL 附加查询参数"""
        if not query_params:
            return url
        if "?" in url:
            return f"{url}&{query_params[1:]}"
        return f"{url}{query_params}"

class CacheInfo(BaseModel):
    """缓存信息"""
    metadata: MetaData

    @computed_field
    @property
    def id(self) -> str:
        return hash_func(self.metadata.url.encode('utf-8')).hexdigest()[:16]

class ListCacheResponse(BaseModel):
    """缓存列表响应"""
    success: bool
    caches: list[CacheInfo]
    total_count: int
