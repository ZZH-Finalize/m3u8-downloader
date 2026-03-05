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
        下载所有分片（多轮重试）

        Args:
            segments: 分片信息列表

        Returns:
            下载结果列表
        """
        # 初始化缓存目录
        self.cache_manager.init_cache()

        # 检查是否有元数据缓存
        metadata = self.config.metadata

        if metadata and metadata.is_complete:
            # 所有分片都已下载，直接返回已存在的路径
            logger.info("所有分片已下载完成，跳过下载阶段")
            results = []
            for seg in segments:
                local_path = self.cache_manager.get_segment_path(seg.filename)
                results.append(DownloadResult(
                    segment=seg,
                    success=True,
                    local_path=local_path,
                    skipped=True
                ))
            return results

        # 多轮下载，直到所有分片完成或达到最大轮次
        max_rounds = self.config.max_download_rounds
        all_results: dict[int, DownloadResult] = {}  # 用索引作为 key 存储结果

        for round_num in range(1, max_rounds + 1):
            logger.info(f"=== 第 {round_num}/{max_rounds} 轮下载 ===")

            # 获取需要下载的分片
            segments_to_download = self._get_segments_to_download(segments, all_results)

            if not segments_to_download:
                logger.info("所有分片已下载完成")
                break

            # 执行本轮下载
            round_results = self._download_round(segments_to_download, len(segments))

            # 合并结果
            for result in round_results:
                all_results[result.segment.index] = result

            # 更新元数据 mask（每轮结束后写入文件）
            if metadata:
                self._update_metadata_mask()

            # 检查本轮完成情况
            success_count = sum(1 for r in round_results if r.success)
            logger.info(f"本轮完成：{success_count}/{len(segments_to_download)} 个分片")

            # 检查是否还有缺失的分片
            missing = self._get_missing_indices(segments, all_results)
            if not missing:
                logger.info("所有分片下载成功")
                break
            else:
                logger.info(f"还有 {len(missing)} 个分片未下载成功，将继续重试")

        # 最终检查
        final_missing = self._get_missing_indices(segments, all_results)
        if final_missing:
            logger.warning(f"下载完成，仍有 {len(final_missing)} 个分片下载失败：{final_missing}")
        else:
            logger.info(f"下载完成，共 {len(segments)} 个分片")

        # 按索引排序返回结果
        results = [all_results[i] for i in range(len(segments)) if i in all_results]
        return results

    def _get_segments_to_download(
        self,
        segments: list[SegmentInfo],
        existing_results: dict[int, DownloadResult]
    ) -> list[SegmentInfo]:
        """
        获取需要下载的分片列表

        Args:
            segments: 所有分片
            existing_results: 已有的下载结果

        Returns:
            需要下载的分片列表
        """
        # 先检查缓存中已存在的分片
        missing_indices = self._get_missing_indices(segments, existing_results)
        return [seg for seg in segments if seg.index in missing_indices]

    def _get_missing_indices(
        self,
        segments: list[SegmentInfo],
        existing_results: dict[int, DownloadResult]
    ) -> list[int]:
        """
        获取未下载成功的分片索引

        Args:
            segments: 所有分片
            existing_results: 已有的下载结果

        Returns:
            未下载成功的分片索引列表
        """
        missing = []
        for seg in segments:
            if seg.index not in existing_results:
                # 还没有尝试下载
                missing.append(seg.index)
            elif not existing_results[seg.index].success:
                # 下载失败，需要重试
                missing.append(seg.index)
        return missing

    def _download_round(
        self,
        segments_to_download: list[SegmentInfo],
        total_segments: int
    ) -> list[DownloadResult]:
        """
        执行一轮下载

        Args:
            segments_to_download: 本轮需要下载的分片
            total_segments: 总分片数

        Returns:
            下载结果列表
        """
        # 统计已存在的分片
        existing_count = sum(
            1 for seg in segments_to_download
            if self.cache_manager.segment_exists(seg.filename)
        )
        if existing_count:
            logger.info(f"发现 {existing_count} 个已存在的分片，将跳过下载")

        # 需要下载的分片数
        to_download = len(segments_to_download) - existing_count
        if to_download > 0:
            logger.info(f"开始下载 {to_download} 个分片，使用 {self.threads} 个线程...")
        else:
            logger.info("所有分片已存在，无需下载")

        # 多线程下载
        results = []
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {
                executor.submit(
                    self._download_segment,
                    seg,
                    total_segments
                ): seg
                for seg in segments_to_download
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        # 按索引排序
        results.sort(key=lambda r: r.segment.index)
        return results

    def _update_metadata_mask(self) -> None:
        """更新元数据中的 downloaded_mask"""
        if self.config.metadata:
            # 根据实际文件状态更新 mask
            metadata = self.cache_manager.update_metadata_downloaded_mask()
            if metadata:
                self.config.metadata = metadata
            logger.debug(f"元数据 downloaded_mask 已更新")

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
