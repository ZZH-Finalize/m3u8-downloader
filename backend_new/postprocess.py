from models import TaskStatus
from task import DownloadTask
from logger import get_logger

logger = get_logger(__name__)

async def merge_segments(task: DownloadTask):
    task.state = TaskStatus.MERGING
    logger.info(f'[{task.id}] 开始后处理')
