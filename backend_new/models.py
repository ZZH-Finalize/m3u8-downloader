from bitarray import bitarray
from pydantic import BaseModel, Field, field_serializer, field_validator
from typing import Optional
from enum import Enum
from datetime import datetime

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
    model_config = {'arbitrary_types_allowed': True}

    url: str
    base_url: str

    output_name: str = 'video.mp4'
    state: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    downloaded_mask: bitarray = Field(default_factory=bitarray)
    segments_num: int = 0
    segments: list[str] = []

    @field_serializer('downloaded_mask')
    def serialize_downloaded_mask(self, value: bitarray) -> str:
        """将 bitarray 序列化为十六进制字符串"""
        return value.tobytes().hex()

    @field_validator('downloaded_mask', mode='before')
    @classmethod
    def deserialize_downloaded_mask(cls, value):
        """从十六进制字符串反序列化为 bitarray"""
        if isinstance(value, bitarray):
            return value

        if isinstance(value, str):
            result = bitarray()
            result.frombytes(bytes.fromhex(value))
            return result

        return bitarray()


class CacheInfo(BaseModel):
    """缓存信息"""
    id: str
    metadata: MetaData

class ListCacheResponse(BaseModel):
    """缓存列表响应"""
    success: bool
    caches: list[CacheInfo]
    total_count: int

class SegmentInfo(BaseModel):
    """分片信息"""
    id: int
    url: str
