import os
import asyncio, aiohttp

from models import TaskStatus, SegmentInfo
from task import DownloadTask
from logger import get_logger
from urllib.parse import urlparse, unquote, urljoin

logger = get_logger(__name__)

MAX_RETRY = 5
MAX_ROUND = 5

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

async def download_segment(session: aiohttp.ClientSession, task: DownloadTask):
    # 未完成持续运行
    while(False == task.complete.is_set()):
        # 检测允许事件
        await task.continue_evt.wait()

        try:
            segment = await asyncio.wait_for(task.url_queue.get(), timeout=1)
        except asyncio.TimeoutError:
            continue

        if segment is None:
            task.complete.set()
            task.url_queue.task_done()
            break

        url_fn = os.path.basename(unquote(urlparse(segment.url).path))
        abs_url = urljoin(task.metadata.base_url, segment.url)

        for i in range(MAX_RETRY):
            logger.info(f'[{task.id}] 下载分片[{segment.id + 1}/{task.metadata.segments_num}]')

            try:
                async with session.get(abs_url) as response:
                    response.raise_for_status()
                    content = await response.read()
                    await task.save_segment(url_fn, segment.id, content)
                    logger.debug(f'[{task.id}] 保存分片文件: {url_fn}')
                    break
            except Exception:
                logger.error(f'[{task.id}] 分片下载失败, 重试[{i + 1}/{MAX_RETRY}]')

        task.url_queue.task_done()

async def download_round(session: aiohttp.ClientSession, task: DownloadTask):
    tasks = [asyncio.create_task(download_segment(session, task)) for _ in range(task.threads)]

    await asyncio.gather(*tasks)
    # await task.url_queue.join()
    await task.flush_cache()

async def download_segments(task: DownloadTask):
    task.state = TaskStatus.DOWNLOADING
    logger.info(f'[{task.id}] 开始下载: {task.url}')
    # 设置执行标志
    task.continue_evt.set()

    # 创建 aiohttp session
    timeout = aiohttp.ClientTimeout(total=10)
    connector = aiohttp.TCPConnector(limit=task.threads)

    try:
        async with aiohttp.ClientSession(headers=HEADERS,
                                        timeout=timeout,
                                        connector=connector
        ) as session:
            for i in range(MAX_ROUND):
                logger.info(f'[{task.id}] ==========第 {i + 1} 轮下载==========')
                failed_bits = task.metadata.downloaded_mask.search(0)
                failed_segments = [SegmentInfo(id=j, url=task.metadata.segments[j])
                            for j in failed_bits]

                if not failed_segments:
                    logger.info(f'[{task.id}] 所有分片均已下载完成')
                    break

                logger.info(f'[{task.id}] 本轮需要下载 {len(failed_segments)} 个分片')

                for segment in failed_segments:
                    task.url_queue.put_nowait(segment)

                task.url_queue.put_nowait(None)

                await download_round(session, task)
    except Exception as e:
        logger.error(f'[{task.id}] 下载过程中出现异常：{e}')
        raise




