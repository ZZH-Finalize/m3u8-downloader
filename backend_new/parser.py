"""
异步 m3u8 解析模块
支持多分辨率 m3u8 解析
"""

import os
import aiohttp
import aiofiles
import m3u8

from task import DownloadTask
from models import TaskStatus
from logger import get_logger
from config import server_config as config
from urllib.parse import urlparse, unquote
from bitarray import bitarray

logger = get_logger(__name__)

async def fetch_m3u8(task_id: str, url: str) -> m3u8.M3U8:
    try:
        logger.info(f'获取m3u8文件: {url}')
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                m3u8_content = await response.text()

        filename = os.path.basename(unquote(urlparse(url).path))

        async with aiofiles.open(config.temp_dir / task_id / filename, 'w') as f:
            await f.write(m3u8_content)

        return m3u8.loads(m3u8_content, uri=url)

    except Exception as e:
        logger.error(f'获取m3u8文件失败: {e}')
        raise

async def parse_m3u8(task: DownloadTask):
    task.state = TaskStatus.PARSING
    m3u8_obj = await fetch_m3u8(task.id, task.url)

    # already is filelist
    if False == m3u8_obj.is_variant:
        selected_m3u8 = m3u8_obj
    else:
        logger.info(f'[{task.id}] 检测到多分辨率媒体')

        # process playlists
        playlists = m3u8_obj.playlists
        # sort based on resolution
        playlists.sort(key=lambda x: x.stream_info.resolution[1], reverse=True)
        # first is the best resolution
        best_resolution = playlists[0]
        logger.info(f'[{task.id}] 自动选择最优分辨率: {best_resolution.stream_info.resolution[0]}x{best_resolution.stream_info.resolution[1]}')
        # fetch best m3u8
        best_m3u8 = await fetch_m3u8(task.id, best_resolution.absolute_uri)
        selected_m3u8 = best_m3u8

    task.metadata.base_url = selected_m3u8.base_uri
    task.metadata.segments = selected_m3u8.files.copy()
    task.metadata.segments_num = len(task.metadata.segments)
    task.metadata.downloaded_mask = bitarray(task.metadata.segments_num)
    task.metadata.downloaded_mask.setall(0)

    await task.flush_cache()
