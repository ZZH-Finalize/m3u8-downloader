from pydantic import BaseModel, Field, computed_field
from typing import Optional
from enum import Enum
from datetime import datetime
from hashlib import md5 as hash_func
from config import server_config as config
import aiofiles


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待中
    PARSING = "parsing"           # 解析中
    DOWNLOADING = "downloading"   # 下载中
    MERGING = "merging"           # 合并中
    PAUSED = "paused"             # 已暂停
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


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
    segments: list[str] = []  # 分片 URL 列表
    downloaded_mask: int = 0
    totol_slice: int = 0
    output_name: str = 'video.mp4'

class CacheInfo(BaseModel):
    """缓存信息"""
    metadata: MetaData

    @computed_field
    @property
    def id(self) -> str:
        return hash_func(self.metadata.url.encode('utf-8')).hexdigest()[:16]
    
    async def flush(self):
        async with aiofiles.open(config.temp_dir / self.id / 'metadata.json', "w") as f:
            await f.write(self.metadata.model_dump_json())

class ListCacheResponse(BaseModel):
    """缓存列表响应"""
    success: bool
    caches: list[CacheInfo]
    total_count: int
