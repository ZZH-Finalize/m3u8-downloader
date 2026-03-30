import quart
import config

from bitarray import bitarray
from pydantic import BaseModel, Field, field_serializer, field_validator
from enum import Enum
from datetime import datetime

class OutputEncoding(str, Enum):
    COPY = "copy"
    H264 = "h264"
    HEVC = "hevc"
    AV1 = "av1"

class Encoder(str, Enum):
    Software = "software"

    # 厂商特定
    NVENC = "nvenc"
    QSV = "qsv"
    AMF = "amf"

    # Linux
    VAAPI = "vaapi"

    # Windows
    MF = "mf"
    D3D12VA = "d3d12va"

    # 跨平台
    VULKAN = "vulkan"
    

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
    threads: int = config.server.max_threads
    output_name: str = 'output.mp4'
    encoder: Encoder = Encoder.Software
    output_encoding: OutputEncoding = OutputEncoding.COPY
    max_rounds: int = 5
    max_retry: int = 5
    keep_cache: bool = False
    queued: bool = False

class MetaData(BaseModel):
    """缓存元数据"""
    model_config = {'arbitrary_types_allowed': True}

    url: str = Field(frozen=True)
    base_url: str = ''

    created_at: datetime = Field(default_factory=datetime.now)
    segments_num: int = 0
    downloaded_mask: bitarray = Field(default_factory=bitarray)
    segments: list[str] = []

    @field_serializer('downloaded_mask')
    def serialize_downloaded_mask(self, value: bitarray) -> str:
        """将 bitarray 序列化为十六进制字符串"""
        return value.tobytes().hex()

    @field_validator('downloaded_mask', mode='before')
    @classmethod
    def deserialize_downloaded_mask(cls, value, info):
        """从十六进制字符串反序列化为 bitarray"""
        if isinstance(value, bitarray):
            return value

        if isinstance(value, str):
            result = bitarray()
            result.frombytes(bytes.fromhex(value))
            # 根据 segments_num 截断到正确长度，避免字节填充导致的多余位
            if 'segments_num' in info.data and info.data['segments_num'] > 0:
                result = result[:info.data['segments_num']]
            return result

        return bitarray()

class Response(BaseModel):
    status_code: int = Field(default=200, exclude=True)

    def unpack(self):
        return quart.jsonify(self.model_dump(mode='json')), self.status_code

class ErrorResponse(Response):
    status_code: int = Field(exclude=True) # pyright: ignore[reportGeneralTypeIssues]
    msg: str

class DownloadResponse(Response):
    """下载任务响应"""
    task_id: str

class TaskInfo(BaseModel):
    """任务信息"""
    url: str
    task_id: str
    state: TaskStatus
    segments_downloaded: int
    total_segments: int
    output_name: str

class GetTaskResponse(TaskInfo, Response):
    """获取单个任务响应"""
    pass

class ListTaskResponse(Response):
    """任务列表响应"""
    tasks: list[TaskInfo]
    total_count: int

class CacheInfo(BaseModel):
    """缓存信息"""
    id: str
    url: str
    created_at: datetime
    segments_num: int

class GetCacheResponse(MetaData, Response):
    """获取单个缓存响应"""
    id: str

class ListCacheResponse(Response):
    """缓存列表响应"""
    caches: list[CacheInfo]
    total_count: int

class SegmentInfo(BaseModel):
    """分片信息"""
    id: int
    url: str
