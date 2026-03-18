import asyncio

from models import TaskStatus
from task import DownloadTask
from logger import get_logger

logger = get_logger('downloader')

MAX_RETRY = 5
MAX_ROUND = 5

async def download_round(task: DownloadTask):
    if task.semaphore.acquire():
        pass

async def download_segments(task: DownloadTask):
    task.state = TaskStatus.DOWNLOADING
    logger.info(f'[{task.id}] 开始下载')

    for i in range(MAX_ROUND):
        logger.info(f'[{task.id}] ==========第{i}轮下载==========')
        

