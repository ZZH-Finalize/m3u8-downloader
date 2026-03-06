#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据模型定义
模块间交互的数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from pathlib import Path


@dataclass
class SegmentInfo:
    """分片信息"""
    url: str
    index: int
    filename: str

    def __hash__(self):
        return hash(self.url)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "url": self.url,
            "index": self.index,
            "filename": self.filename
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SegmentInfo":
        """从字典创建"""
        return cls(
            url=data["url"],
            index=data["index"],
            filename=data["filename"]
        )


@dataclass
class MetaData:
    """
    缓存元数据

    优化格式：
    - filenames: 只保存文件名列表（不包含完整 URL）
    - downloaded_mask: 位掩码，标注已下载的分片（1=已下载，0=未下载）
    """
    url: str  # 原始 m3u8 URL
    base_url: str  # 基准 URL
    filenames: list[str]  # 分片文件名列表
    downloaded_mask: int = 0  # 已下载分片的位掩码
    created_at: str = ""  # 创建时间 (ISO 格式)
    version: str = "1.0"  # 元数据版本

    # 分片数量上限
    MAX_SEGMENTS = 10000  # bitmask 最大容纳 10000 个分片

    def __post_init__(self):
        """初始化时设置默认值并检查上限"""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

        # 检查分片数量是否超过上限
        if len(self.filenames) > self.MAX_SEGMENTS:
            raise ValueError(
                f"分片数量 {len(self.filenames)} 超过上限 {self.MAX_SEGMENTS}"
            )

    @property
    def total_mask(self) -> int:
        """计算完整掩码（所有位都是 1）"""
        if not self.filenames:
            return 0
        return (1 << len(self.filenames)) - 1

    @property
    def is_complete(self) -> bool:
        """检查是否所有分片都已下载"""
        return self.downloaded_mask == self.total_mask and len(self.filenames) > 0

    def is_segment_downloaded(self, index: int) -> bool:
        """
        检查指定索引的分片是否已下载

        Args:
            index: 分片索引

        Returns:
            是否已下载
        """
        if index < 0 or index >= len(self.filenames):
            return False
        return bool(self.downloaded_mask & (1 << index))

    def set_segment_downloaded(self, index: int) -> None:
        """
        标记指定索引的分片为已下载

        Args:
            index: 分片索引
        """
        if 0 <= index < len(self.filenames):
            self.downloaded_mask |= (1 << index)

    def get_missing_indices(self) -> list[int]:
        """
        获取未下载分片的索引列表

        Returns:
            未下载分片的索引列表
        """
        missing = []
        for i in range(len(self.filenames)):
            if not self.is_segment_downloaded(i):
                missing.append(i)
        return missing

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "version": self.version,
            "url": self.url,
            "base_url": self.base_url,
            "filenames": self.filenames,
            "downloaded_mask": self.downloaded_mask,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetaData":
        """从字典创建"""
        return cls(
            version=data.get("version", "1.0"),
            url=data["url"],
            base_url=data["base_url"],
            filenames=data["filenames"],
            downloaded_mask=data.get("downloaded_mask", 0),
            created_at=data.get("created_at", "")
        )


@dataclass
class DownloadResult:
    """下载结果"""
    segment: SegmentInfo
    success: bool
    local_path: Optional[Path] = None
    error: Optional[str] = None
    skipped: bool = False  # 是否因已存在而跳过


@dataclass
class ParseResult:
    """解析结果"""
    segments: list[SegmentInfo]
    base_url: str
    success: bool
    error: Optional[str] = None


@dataclass
class MergeResult:
    """合并结果"""
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AppConfig:
    """应用配置 - 统一在 main 中获取并分发给各模块"""
    # 输入
    url: str

    # 下载配置
    threads: int = 4
    timeout: int = 30
    retry_count: int = 3
    max_download_rounds: int = 5  # 最大下载轮次

    # 路径配置
    temp_dir: str = "temp_segments"
    output_dir: str = "output"  # 输出目录
    keep_cache: bool = False  # 是否保留缓存

    # 外部工具配置
    ffmpeg_path: str = "ffmpeg"  # ffmpeg 路径（可通过环境变量 FFMPEG_PATH 设置）

    # 运行时生成
    parsed_segments: list[SegmentInfo] = field(default_factory=list)
    downloaded_paths: list[Path] = field(default_factory=list)
    m3u8_content: str = ""  # m3u8 源文件内容
    output_file: str = ""  # 最终输出文件路径（运行时生成）
    metadata: Optional["MetaData"] = None  # 元数据缓存
