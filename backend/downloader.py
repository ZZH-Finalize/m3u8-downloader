#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步下载模块
使用 aiohttp 实现异步下载，支持高并发
"""

import asyncio
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import ClientError

from models import AppConfig, SegmentInfo, DownloadResult
from cache_manager import CacheManager
from logger import get_logger

logger = get_logger("downloader")


class SegmentDownloader:
    """异步分片下载器"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    def __init__(
        self,
        config: AppConfig,
        cache_manager: CacheManager,
        progress_callback=None
    ):
        self.config = config
        self.cache_manager = cache_manager
        self.timeout = config.timeout
        self.retry_count = config.retry_count
        self.threads = config.threads  # 实际是并发连接数
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._progress_callback = progress_callback  # 进度回调函数
        self._completed_count = 0  # 已完成计数（成功下载的分片数）
        self._total_count = 0      # 总数量

    async def download_all(
        self,
        segments: list[SegmentInfo]
    ) -> list[DownloadResult]:
        """
        异步下载所有分片（多轮重试）

        Args:
            segments: 分片信息列表

        Returns:
            下载结果列表
        """
        # 初始化缓存目录
        self.cache_manager.init_cache()

        # 初始化进度计数
        self._total_count = len(segments)
        self._completed_count = 0

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
            round_results = await self._download_round(segments_to_download, len(segments))

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
        """获取需要下载的分片列表"""
        missing_indices = self._get_missing_indices(segments, existing_results)
        return [seg for seg in segments if seg.index in missing_indices]

    def _get_missing_indices(
        self,
        segments: list[SegmentInfo],
        existing_results: dict[int, DownloadResult]
    ) -> list[int]:
        """获取未下载成功的分片索引"""
        return [
            seg.index for seg in segments
            if seg.index not in existing_results or not existing_results[seg.index].success
        ]

    async def _download_round(
        self,
        segments_to_download: list[SegmentInfo],
        total_segments: int
    ) -> list[DownloadResult]:
        """执行一轮下载"""
        # 统计已存在的分片
        existing_count = sum(
            1 for seg in segments_to_download
            if self.cache_manager.segment_exists(seg.filename)
        )

        to_download = len(segments_to_download) - existing_count
        if existing_count:
            logger.info(f"发现 {existing_count} 个已存在的分片，将跳过下载")
        if to_download > 0:
            logger.info(f"开始下载 {to_download} 个分片，并发数：{self.threads}...")
        else:
            logger.info("所有分片已存在，无需下载")

        # 创建信号量控制并发
        self._semaphore = asyncio.Semaphore(self.threads)

        # 创建 aiohttp session
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        connector = aiohttp.TCPConnector(limit=self.threads)

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=self.HEADERS
        ) as self._session:
            # 创建下载任务
            tasks = [
                self._download_segment(seg, total_segments)
                for seg in segments_to_download
            ]
            # 并发执行
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        download_results = [
            r for r in results
            if not isinstance(r, Exception)
        ]
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"下载任务异常：{result}")

        # 按索引排序
        download_results.sort(key=lambda r: r.segment.index)
        return download_results

    def _update_metadata_mask(self) -> None:
        """更新元数据中的 downloaded_mask"""
        if self.config.metadata:
            metadata = self.cache_manager.update_metadata_downloaded_mask()
            if metadata:
                self.config.metadata = metadata

    async def _download_segment(
        self,
        segment: SegmentInfo,
        total: int
    ) -> DownloadResult:
        """异步下载单个分片"""
        async with self._semaphore:
            local_path = self.cache_manager.get_segment_path(segment.filename)

            # 检查是否已下载（断点续传）
            if self.cache_manager.segment_exists(segment.filename):
                logger.info(
                    f"[{segment.index + 1}/{total}] 跳过：{segment.filename} (已存在)"
                )
                self._completed_count += 1
                self._notify_progress()
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
                    async with self._session.get(segment.url) as response:
                        response.raise_for_status()
                        content = await response.read()

                    self.cache_manager.save_segment(segment.filename, content)
                    logger.info(
                        f"[{segment.index + 1}/{total}] 完成：{segment.filename}"
                    )

                    self._completed_count += 1
                    self._notify_progress()

                    return DownloadResult(
                        segment=segment,
                        success=True,
                        local_path=local_path
                    )

                except ClientError as e:
                    error_msg = str(e)
                    logger.warning(
                        f"[{segment.index + 1}/{total}] "
                        f"重试 {attempt + 1}/{self.retry_count}: "
                        f"{segment.filename} - {error_msg}"
                    )
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue

            logger.error(
                f"[{segment.index + 1}/{total}] 失败：{segment.filename} - {error_msg}"
            )

            # 下载失败时不增加计数
            return DownloadResult(
                segment=segment,
                success=False,
                error=error_msg
            )

    def _notify_progress(self):
        """通知进度更新"""
        if self._progress_callback and self._total_count > 0:
            self._progress_callback(self._completed_count, self._total_count)

    def get_success_paths(
        self,
        results: list[DownloadResult]
    ) -> list[Path]:
        """
        从下载结果中提取成功下载的路径
        顺序与 metadata.filenames 一致

        注意：调用此方法前应确保所有分片都已下载成功
        """
        path_map = {
            r.segment.filename: r.local_path
            for r in results
            if r.success and r.local_path
        }

        return [
            path_map[filename]
            for filename in self.config.metadata.filenames
            if filename in path_map
        ]
