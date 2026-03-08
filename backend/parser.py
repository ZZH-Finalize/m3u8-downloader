#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步 m3u8 解析模块
使用 aiohttp 异步解析 m3u8 文件
"""

import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple

import m3u8
import aiohttp
from aiohttp import ClientError

from models import AppConfig, SegmentInfo, ParseResult, MetaData
from cache_manager import CacheManager
from logger import get_logger

logger = get_logger("parser")


class M3u8Parser:
    """异步 m3u8 解析器"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    def __init__(self, config: AppConfig, cache_manager: CacheManager):
        self.config = config
        self.cache_manager = cache_manager
        self.timeout = config.timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def parse(self, force_refresh: bool = False) -> ParseResult:
        """
        异步解析 m3u8 文件

        Args:
            force_refresh: 是否强制刷新，忽略元数据缓存

        Returns:
            ParseResult: 解析结果
        """
        url = self.config.url
        logger.info(f"正在解析：{url}")

        # 检查元数据缓存
        if not force_refresh:
            cached_result = self._try_load_from_metadata_cache()
            if cached_result:
                return cached_result

        # 获取 m3u8 内容
        content = await self._get_m3u8_content(force_refresh)
        if content is None:
            return ParseResult(
                segments=[],
                base_url="",
                success=False,
                error=f"无法获取 m3u8 文件：{url}"
            )

        base_url = self._get_base_url(url)

        try:
            segments = await self._parse_playlist(content, base_url, force_refresh)
        except Exception as e:
            logger.error(f"m3u8 解析失败 - {e}")
            return ParseResult(
                segments=[],
                base_url=base_url,
                success=False,
                error=f"m3u8 解析失败 - {e}"
            )

        if not segments:
            logger.error("未找到任何视频分片")
            return ParseResult(
                segments=[],
                base_url=base_url,
                success=False,
                error="未找到任何视频分片"
            )

        logger.info(f"解析成功，共找到 {len(segments)} 个分片")

        # 保存 m3u8 源文件内容到配置
        self.config.m3u8_content = content

        # 保存元数据到缓存
        try:
            self._save_metadata(url, base_url, segments)
        except ValueError as e:
            logger.error(str(e))
            return ParseResult(
                segments=[],
                base_url=base_url,
                success=False,
                error=str(e)
            )

        return ParseResult(
            segments=segments,
            base_url=base_url,
            success=True
        )

    def _try_load_from_metadata_cache(self) -> Optional[ParseResult]:
        """尝试从元数据缓存加载，成功则返回 ParseResult"""
        if not self.cache_manager.metadata_exists():
            return None

        logger.info("检测到元数据缓存，尝试从缓存加载")
        metadata = self.cache_manager.load_metadata()
        if metadata and metadata.url == self.config.url:
            logger.info(f"元数据匹配，使用缓存的解析结果（共 {len(metadata.filenames)} 个分片）")

            # 更新 downloaded_mask（根据实际文件状态）
            self.cache_manager.update_metadata_downloaded_mask()

            # 从元数据重建 SegmentInfo 列表
            segments = self._rebuild_segments_from_metadata(metadata)

            # 保存元数据到配置
            self.config.metadata = metadata
            self.config.m3u8_content = ""

            downloaded_count = metadata.get_downloaded_count()
            logger.info(f"已下载 {downloaded_count}/{len(metadata.filenames)} 个分片")

            return ParseResult(
                segments=segments,
                base_url=metadata.base_url,
                success=True
            )
        else:
            logger.info("元数据 URL 不匹配，将重新解析")
        return None

    async def _get_m3u8_content(self, force_refresh: bool) -> Optional[str]:
        """获取 m3u8 内容（从缓存或网络）"""
        if not force_refresh and self.cache_manager.master_m3u8_exists():
            logger.info("检测到主 m3u8 缓存，从缓存加载")
            return self.cache_manager.load_master_m3u8()

        logger.info("从网络获取 m3u8 文件")
        content = await self._fetch_url(self.config.url)
        if content:
            self.cache_manager.save_master_m3u8(content)
        return content

    async def _parse_playlist(
        self,
        content: str,
        base_url: str,
        force_refresh: bool
    ) -> list[SegmentInfo]:
        """解析 m3u8 内容，处理 Master Playlist 和子 Playlist"""
        playlist = m3u8.loads(content)
        playlist.base_uri = self.config.url

        # 检查是否是 Master Playlist
        if not playlist.playlists:
            return self._extract_segments(playlist, base_url)

        logger.info(f"检测到 Master Playlist，包含 {len(playlist.playlists)} 个子列表")

        # 选择最高分辨率的子 playlist
        best_playlist = max(
            playlist.playlists,
            key=lambda p: p.stream_info.resolution or (0, 0)
        )
        best_resolution = best_playlist.stream_info.resolution
        logger.info(f"选择最高分辨率：{best_resolution}")

        sub_content = await self._get_sub_playlist_content(
            best_playlist, best_resolution, force_refresh
        )
        if sub_content is None:
            raise Exception(f"无法获取子 m3u8 文件：{best_playlist.absolute_uri}")

        # 缓存其他分辨率
        await self._cache_other_resolutions(playlist, best_resolution)

        sub_playlist = m3u8.loads(sub_content)
        sub_playlist.base_uri = best_playlist.absolute_uri
        return self._extract_segments(sub_playlist, base_url)

    async def _get_sub_playlist_content(
        self,
        playlist: m3u8.Playlist,
        resolution: Tuple[int, int],
        force_refresh: bool
    ) -> Optional[str]:
        """获取子 playlist 内容（从缓存或网络）"""
        if not force_refresh and self.cache_manager.resolution_m3u8_exists(resolution):
            logger.info(f"检测到分辨率 {resolution} 的 m3u8 缓存，从缓存加载")
            return self.cache_manager.load_resolution_m3u8(resolution)

        logger.info(f"从网络获取子 playlist: {playlist.absolute_uri}")
        content = await self._fetch_url(playlist.absolute_uri)
        if content:
            self.cache_manager.save_resolution_m3u8(resolution, content)
        return content

    async def _cache_other_resolutions(
        self,
        playlist: m3u8.M3U8,
        best_resolution: Tuple[int, int]
    ) -> None:
        """异步缓存其他分辨率的子 playlist"""
        tasks = [
            self._fetch_and_cache_resolution(sub_playlist)
            for sub_playlist in playlist.playlists
            if sub_playlist.stream_info.resolution
            and sub_playlist.stream_info.resolution != best_resolution
            and not self.cache_manager.resolution_m3u8_exists(sub_playlist.stream_info.resolution)
        ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_and_cache_resolution(self, sub_playlist: m3u8.Playlist) -> None:
        """获取并缓存单个分辨率的 m3u8 文件"""
        resolution = sub_playlist.stream_info.resolution
        url = sub_playlist.absolute_uri
        logger.info(f"缓存分辨率 {resolution} 的 m3u8 文件：{url}")
        try:
            content = await self._fetch_url(url)
            if content:
                self.cache_manager.save_resolution_m3u8(resolution, content)
        except Exception as e:
            logger.warning(f"无法获取分辨率 {resolution} 的 m3u8 文件：{e}")

    async def _fetch_url(self, url: str) -> Optional[str]:
        """异步获取 URL 内容"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout, headers=self.HEADERS) as session:
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return await response.text()
            except ClientError as e:
                logger.error(f"无法获取 URL - {e}")
                return None

    def _rebuild_segments_from_metadata(self, metadata: MetaData) -> list[SegmentInfo]:
        """从元数据重建分片信息列表"""
        segments = []
        for index, filename in enumerate(metadata.filenames):
            # 合成完整 URL
            url = metadata.base_url + filename if not filename.startswith("http") else filename
            segments.append(SegmentInfo(
                url=url,
                index=index,
                filename=filename
            ))
        return segments

    def _save_metadata(self, url: str, base_url: str, segments: list[SegmentInfo]) -> None:
        """保存元数据到缓存"""
        filenames = [seg.filename for seg in segments]

        if len(filenames) > MetaData.MAX_SEGMENTS:
            logger.error(
                f"分片数量 {len(filenames)} 超过上限 {MetaData.MAX_SEGMENTS}，"
                f"bitmask 无法容纳，请手动处理"
            )
            raise ValueError(
                f"分片数量过多 ({len(filenames)})，超过上限 {MetaData.MAX_SEGMENTS}"
            )

        metadata = MetaData(
            url=url,
            base_url=base_url,
            filenames=filenames,
            downloaded_mask=0,
            created_at=datetime.now().isoformat()
        )
        self.cache_manager.save_metadata(metadata)
        logger.debug(f"元数据已保存到缓存")

    def _get_base_url(self, url: str) -> str:
        """获取 URL 的基准路径"""
        parsed = urlparse(url)
        path = parsed.path

        if "/" in path:
            path = path.rsplit("/", 1)[0] + "/"

        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _extract_segments(
        self,
        playlist: m3u8.M3U8,
        base_url: str
    ) -> list[SegmentInfo]:
        """从 m3u8 playlist 中提取分片"""
        segments = []

        for index, segment in enumerate(playlist.segments):
            segment_url = segment.absolute_uri
            if segment_url:
                filename = self._get_segment_filename(segment_url, base_url, index)
                segments.append(SegmentInfo(
                    url=segment_url,
                    index=index,
                    filename=filename
                ))

        return segments

    def _get_segment_filename(
        self,
        url_path: str,
        base_url: str,
        index: int
    ) -> str:
        """
        生成分片文件名（相对于 base_url 的路径）

        Args:
            url_path: 分片的完整 URL
            base_url: 基准 URL
            index: 分片索引

        Returns:
            相对于 base_url 的文件路径
        """
        parsed = urlparse(url_path)
        full_path = parsed.path.lstrip("/")

        # 从 base_url 中提取路径部分
        base_parsed = urlparse(base_url)
        base_path = base_parsed.path.lstrip("/")

        # 如果 full_path 以 base_path 开头，则去掉前缀
        if base_path and full_path.startswith(base_path):
            relative_path = full_path[len(base_path):]
            return relative_path

        # 否则返回完整路径
        if full_path:
            return full_path
        return f"segment_{index:06d}.ts"
