from logger import get_logger
from models import TaskStatus
from task import DownloadTask
from parser import parse_m3u8
from downloader import download_segments
from postprocess import merge_segments
from config import server_config as config

logger = get_logger(__name__)

async def download(url: str, max_threads: int = config.max_threads, output_name: str = 'video.mp4'):
    try:
        task = DownloadTask(url, max_threads, output_name)

        if task.cache_exists():
            logger.info(f'[{task.id}] 元数据文件存在')
            await task.load_cache()
        else:
            await parse_m3u8(task)

        await download_segments(task)
        await merge_segments(task)

        task.state = TaskStatus.COMPLETED
        await task.flush_cache()

    except Exception as e:
        task.state = TaskStatus.FAILED
        logger.error(f'[{task.id}] 任务出现异常: {e}')

