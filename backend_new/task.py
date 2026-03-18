import aiofiles, asyncio

from models import MetaData, SegmentInfo, TaskStatus
from config import server_config as config
from logger import get_logger
from pathlib import Path

logger = get_logger(__name__)

METADATA_FILE_NAME = 'metadata.json'

class DownloadTask:
    def __init__(self, id: str, url: str, max_threads: int, output_name: str) -> None:
        self.id = id
        self.metadata = MetaData(url=url, base_url='')

        self.metadata.output_name = output_name
        self.max_threads = max_threads

        # 待下载分片 queue
        self.url_queue: asyncio.Queue[SegmentInfo | None] = asyncio.Queue()
        # 暂停控制
        self.continue_evt = asyncio.Event()
        # 完成控制
        self.complete = asyncio.Event()

        # 缓存路径
        self.cache_dir = config.temp_dir / self.metadata.id
        self.segments_dir = self.cache_dir / 'segments'
        self.metadata_file = self.cache_dir / METADATA_FILE_NAME

        # 创建任务的cache路径
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.segments_dir.mkdir(parents=True, exist_ok=True)

    @property
    def url(self):
        return self.metadata.url

    @property
    def state(self):
        return self.metadata.state

    @state.setter
    def state(self, state):
        self.metadata.state = state

    def cache_exists(self):
        return self.metadata_file.exists()

    async def load_cache(self):
        try:
            async with aiofiles.open(self.metadata_file, 'r') as f:
                metadata = await f.read()

            self.metadata = MetaData.model_validate_json(metadata)
            logger.info(f'[{self.id}] 载入元数据')
        except Exception as e:
            logger.warning(f'[{self.id}] 元数据加载异常：{e}')
            raise

    async def cache_file(self, fn: Path | str, content, mode: str = 'w'):
        async with aiofiles.open(self.cache_dir / fn, mode) as f: # pyright: ignore[reportArgumentType, reportCallIssue]
            await f.write(content)

    async def flush_cache(self):
        await self.cache_file(METADATA_FILE_NAME, self.metadata.model_dump_json())

    async def save_segment(self, fn: str, id: int, content):
        await self.cache_file(Path('segments') / fn, content, mode='wb')
        self.metadata.downloaded_mask[id] = 1

from parser import parse_m3u8
from downloader import download_segments
from postprocess import merge_segments
from hashlib import md5 as hash_func

task_map: dict[str, DownloadTask] = {}
queue: asyncio.Queue[DownloadTask] = asyncio.Queue()

async def __exec(task: DownloadTask):
    try:
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

async def scheduler():
    while True:
        task = await queue.get()
        await __exec(task)

async def add(url: str, max_threads: int = config.max_threads, output_name: str = 'video.mp4', add_to_queue: bool = False):
    task_id = hash_func(url.encode('utf-8')).hexdigest()[:16]

    if task_id not in task_map:
        task = DownloadTask(task_id, url, max_threads, output_name)
    else:
        task = task_map[task_id]

    if add_to_queue:
        await queue.put(task)
    else:
        asyncio.create_task(__exec(task))

