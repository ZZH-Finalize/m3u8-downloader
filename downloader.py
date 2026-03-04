#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载模块
负责多线程下载分片，支持断点续传
"""

import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.exceptions import RequestException

from models import AppConfig, SegmentInfo, DownloadResult
from logger import get_logger

logger = get_logger("downloader")


class SegmentDownloader:
    """分片下载器"""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.temp_dir = Path(config.temp_dir)
        self.timeout = config.timeout
        self.retry_count = config.retry_count
        self.threads = config.threads
        self._lock = threading.Lock()
    
    def download_all(
        self, 
        segments: list[SegmentInfo]
    ) -> list[DownloadResult]:
        """
        下载所有分片
        
        Args:
            segments: 分片信息列表
            
        Returns:
            下载结果列表
        """
        # 创建输出目录
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计已存在的分片
        existing_count = sum(
            1 for seg in segments 
            if self._get_local_path(seg).exists()
        )
        if existing_count:
            logger.info(f"发现 {existing_count} 个已存在的分片，将跳过下载")
        
        logger.info(f"开始下载，使用 {self.threads} 个线程...")
        
        # 多线程下载
        results = []
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {
                executor.submit(
                    self._download_segment, 
                    seg, 
                    len(segments)
                ): seg
                for seg in segments
            }
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # 按索引排序
        results.sort(key=lambda r: r.segment.index)
        
        return results
    
    def _download_segment(
        self, 
        segment: SegmentInfo, 
        total: int
    ) -> DownloadResult:
        """
        下载单个分片
        
        Args:
            segment: 分片信息
            total: 总分片数
            
        Returns:
            下载结果
        """
        local_path = self._get_local_path(segment)
        
        # 检查是否已下载（断点续传）
        if local_path.exists():
            with self._lock:
                logger.info(
                    f"[{segment.index + 1}/{total}] 跳过：{segment.filename} (已存在)"
                )
            return DownloadResult(
                segment=segment,
                success=True,
                local_path=local_path,
                skipped=True
            )
        
        # 下载
        error_msg = ""
        for attempt in range(self.retry_count):
            try:
                response = requests.get(
                    segment.url,
                    headers=self.HEADERS,
                    timeout=self.timeout,
                    stream=True
                )
                response.raise_for_status()
                
                # 写入临时文件
                temp_path = local_path.with_suffix(
                    local_path.suffix + ".tmp"
                )
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # 重命名为正式文件
                temp_path.rename(local_path)
                
                with self._lock:
                    logger.info(
                        f"[{segment.index + 1}/{total}] 完成：{segment.filename}"
                    )
                
                return DownloadResult(
                    segment=segment,
                    success=True,
                    local_path=local_path
                )
                
            except RequestException as e:
                error_msg = str(e)
                with self._lock:
                    logger.warning(
                        f"[{segment.index + 1}/{total}] "
                        f"重试 {attempt + 1}/{self.retry_count}: "
                        f"{segment.filename} - {error_msg}"
                    )
                if attempt < self.retry_count - 1:
                    continue
        
        logger.error(
            f"[{segment.index + 1}/{total}] 失败：{segment.filename} - {error_msg}"
        )
        return DownloadResult(
            segment=segment,
            success=False,
            error=error_msg
        )
    
    def _get_local_path(self, segment: SegmentInfo) -> Path:
        """获取分片的本地保存路径"""
        return self.temp_dir / segment.filename
    
    def get_success_paths(
        self, 
        results: list[DownloadResult]
    ) -> list[Path]:
        """
        从下载结果中提取成功下载的路径（按顺序）
        
        Args:
            results: 下载结果列表
            
        Returns:
            成功下载的文件路径列表
        """
        success_paths = [
            r.local_path for r in results 
            if r.success and r.local_path
        ]
        success_paths.sort(key=lambda p: p.name)
        return success_paths
