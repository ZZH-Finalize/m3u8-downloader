from logger import get_logger
from models import TaskStatus
from task import DownloadTask
from parser import parse_m3u8
from downloader import download_segments
from postprocess import merge_segments

logger = get_logger('task')

async def download(url: str, output_name: str = 'video.mp4'):
    try:
        task = DownloadTask(url, output_name)

        if task.cache_exists():
            logger.info(f'[{task.id}] 元数据文件存在')
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

