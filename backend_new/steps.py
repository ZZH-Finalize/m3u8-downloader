import logger
from task import DownloadTask

from parser import parse_m3u8
from downloader import download_segments
from postprocess import merge_segments

logging = logger.get_logger('task')


async def download(url: str):
    task = DownloadTask(url)

    if task.cache_exists():
        await task.load_cache()
    else:
        await parse_m3u8(task)

    await download_segments(task)
    await merge_segments(task)

