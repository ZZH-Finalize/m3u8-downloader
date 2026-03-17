from logger import get_logger
from models import TaskStatus
from task import DownloadTask
from parser import parse_m3u8
from downloader import download_segments
from postprocess import merge_segments

logger = get_logger('task')

async def download(url: str):
    try:
        task = DownloadTask(url)

        if task.cache_exists():
            await task.load_cache()
        else:
            await parse_m3u8(task)

        await download_segments(task)
        await merge_segments(task)

        task.state = TaskStatus.COMPLETED
        await task.cache.flush()

    except Exception as e:
        task.state = TaskStatus.FAILED
        logger.error(f'[{task.id}] 任务出现异常: {e.with_traceback(e.__traceback__)}')

