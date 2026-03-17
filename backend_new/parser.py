"""
异步 m3u8 解析模块
支持多分辨率 m3u8 解析
"""

import asyncio
import aiohttp
from aiohttp import ClientError
from typing import Optional

import m3u8

from task import DownloadTask
from logger import get_logger

logger = get_logger('parser')


async def parse_m3u8(task: DownloadTask, timeout: int = 30) -> bool:
    """
    解析 m3u8 文件，支持多分辨率

    Args:
        task: 下载任务对象
        timeout: 请求超时时间

    Returns:
        解析是否成功
    """
    url = task.url
    logger.info(f"正在解析：{url}")

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as session:
            content = await _fetch_url(session, url)
            if not content:
                logger.error(f"无法获取 m3u8 文件：{url}")
                return False

            metadata = task.metadata
            base_url = metadata.get_base_url()
            playlist = m3u8.loads(content)
            playlist.base_uri = url

            # 检查是否是 Master Playlist（多分辨率）
            if playlist.playlists:
                logger.info(f"检测到 Master Playlist，包含 {len(playlist.playlists)} 个子列表")
                # 列出所有分辨率
                for p in playlist.playlists:
                    resolution = p.stream_info.resolution
                    bandwidth = p.stream_info.bandwidth
                    logger.info(f"  - 分辨率：{resolution}, 码率：{bandwidth}")

                # 选择最高分辨率的子 playlist
                best_playlist = max(
                    playlist.playlists,
                    key=lambda p: p.stream_info.resolution or (0, 0)
                )
                best_resolution = best_playlist.stream_info.resolution
                logger.info(f"选择最高分辨率：{best_resolution}")

                # 获取子 playlist 内容
                sub_content = await _fetch_url(session, best_playlist.absolute_uri)
                if not sub_content:
                    logger.error(f"无法获取子 m3u8 文件：{best_playlist.absolute_uri}")
                    return False

                sub_playlist = m3u8.loads(sub_content)
                sub_playlist.base_uri = best_playlist.absolute_uri
                base_url = metadata.get_base_url()
                segment_urls = _extract_segments(metadata, sub_playlist, base_url)
            else:
                # 普通 playlist，直接提取分片
                segment_urls = _extract_segments(metadata, playlist, base_url)

            if not segment_urls:
                logger.error("未找到任何视频分片")
                return False

            logger.info(f"解析成功，共找到 {len(segment_urls)} 个分片")

            # 更新元数据
            metadata.slice_files = segment_urls
            metadata.totol_slice = len(segment_urls)

            return True

    except Exception as e:
        logger.error(f"解析失败：{e}")
        return False


async def _fetch_url(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """异步获取 URL 内容"""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text()
    except ClientError as e:
        logger.error(f"无法获取 URL {url} - {e}")
        return None


def _extract_segments(
    metadata,
    playlist: m3u8.M3U8,
    base_url: str
) -> list[str]:
    """从 m3u8 playlist 中提取分片 URL"""
    segment_urls = []
    query_params = metadata.extract_query_params()

    for segment in playlist.segments:
        segment_url = segment.absolute_uri

        if segment_url:
            # 如果原始 URL 有查询参数，且分片 URL 是相对路径拼接的，需要附加查询参数
            if query_params and metadata.is_relative_segment_url(segment_url, base_url):
                segment_url = metadata.append_query_params(segment_url, query_params)

            segment_urls.append(segment_url)

    return segment_urls
