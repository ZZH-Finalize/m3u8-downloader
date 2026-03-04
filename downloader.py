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
from cache_manager import CacheManager
from logger import get_logger

logger = get_logger("downloader")


class SegmentDownloader:
    """分片下载器"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    def __init__(self, config: AppConfig, cache_manager: CacheManager):
        self.config = config
        self.cache_manager = cache_manager
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
        # 初始化缓存目录
        self.cache_manager.init_cache()

        # 统计已存在的分片
        existing_count = sum(
            1 for seg in segments
            if self.cache_manager.segment_exists(seg.filename)
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
        local_path = self.cache_manager.get_segment_path(segment.filename)

        # 检查是否已下载（断点续传）
        if self.cache_manager.segment_exists(segment.filename):
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

                # 写入缓存
                self.cache_manager.save_segment(segment.filename, response.content)

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
