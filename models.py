#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据模型定义
模块间交互的数据结构
"""

from dataclasses import dataclass, field
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
    
    # 路径配置
    temp_dir: str = "temp_segments"
    output_file: str = "video.mp4"
    
    # 运行时生成
    parsed_segments: list[SegmentInfo] = field(default_factory=list)
    downloaded_paths: list[Path] = field(default_factory=list)
