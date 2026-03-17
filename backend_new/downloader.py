from models import TaskStatus
from task import DownloadTask
from logger import get_logger

logger = get_logger('downloader')

async def download_segments(task: DownloadTask):
    task.state = TaskStatus.DOWNLOADING
    logger.info(f'[{task.id}] 开始下载')
