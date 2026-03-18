import aiofiles, asyncio
import config

from models import MetaData, SegmentInfo, TaskStatus, TaskInfo, ListTaskResponse
from logger import get_logger
from pathlib import Path

logger = get_logger(__name__)

METADATA_FILE_NAME = 'metadata.json'

class DownloadTask:
    def __init__(self, id: str, url: str, threads: int, output_name: str, keep_cache: bool = False) -> None:
        self.id = id
        self.metadata = MetaData(url=url, base_url='')

        self.metadata.output_name = output_name
        self.threads = threads
        self.keep_cache = keep_cache

        self.old_state = TaskStatus.PENDING

        # 待下载分片 queue
        self.url_queue: asyncio.Queue[SegmentInfo | None] = asyncio.Queue()
        # 暂停控制
        self.continue_evt = asyncio.Event()
        # 完成控制
        self.complete = asyncio.Event()

        # 缓存路径
        self.cache_dir = config.server.temp_dir / self.id
        self.segments_dir = self.cache_dir / config.server.segments_dir
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

    def pause(self):
        if self.state not in (TaskStatus.PENDING, TaskStatus.PARSING, TaskStatus.DOWNLOADING):
            return

        logger.info(f'[{self.id}] 暂停执行')

        self.continue_evt.clear()
        self.old_state = self.state
        self.state = TaskStatus.PAUSED

    def resume(self):
        if self.state != TaskStatus.PAUSED:
            return

        logger.info(f'[{self.id}] 恢复执行')

        self.continue_evt.set()
        self.state = self.old_state

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
        await self.cache_file(config.server.segments_dir / fn, content, mode='wb')
        self.metadata.downloaded_mask[id] = 1

    def to_response(self) -> TaskInfo:
        return TaskInfo(task_id=self.id, 
                        segments_downloaded=self.metadata.downloaded_mask.count(),
                        total_segments=self.metadata.segments_num,
                        output_name=self.metadata.output_name)

from parser import parse_m3u8
from downloader import download_segments
from postprocess import merge_segments, clear_segments
from hashlib import md5 as hash_func

task_map: dict[str, DownloadTask] = {}
queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
current_queued_task: DownloadTask | None = None

async def __exec(task: DownloadTask, queued: bool = False):
    try:
        if False == queued and current_queued_task is not None:
            # 并发任务启动时, 暂停队列任务
            current_queued_task.pause()

        if task.cache_exists():
            logger.info(f'[{task.id}] 元数据文件存在')
            await task.load_cache()
        else:
            await parse_m3u8(task)

        await download_segments(task)
        await merge_segments(task)

        if False == task.keep_cache:
            clear_segments(task)

        task.state = TaskStatus.COMPLETED
        await task.flush_cache()

    except Exception as e:
        task.state = TaskStatus.FAILED
        logger.error(f'[{task.id}] 任务出现异常: {e}')
    
    finally:
        if False == queued and current_queued_task is not None:
            # 并发任务结束后, 恢复队列任务
            current_queued_task.resume()

async def queued_task_executor():
    global current_queued_task

    while True:
        task = await queue.get()
        current_queued_task = task
        await __exec(task, True)
        current_queued_task = None

async def add(url: str, threads: int = config.server.max_threads, output_name: str = 'video.mp4', keep_cache: bool = False, queued: bool = False):
    task_id = hash_func(url.encode('utf-8')).hexdigest()[:16]

    if task_id  in task_map:
        return None

    task = DownloadTask(task_id, url, threads, output_name, keep_cache)

    if queued:
        await queue.put(task)
    else:
        asyncio.create_task(__exec(task))

    return task

def list_task() -> ListTaskResponse:
    tasks = ListTaskResponse(success=True)

    for task in task_map.values():
        tasks.tasks.append(task.to_response())

    tasks.total_count = len(tasks.tasks)

    return tasks

def get(task_id: str) -> TaskInfo | None:
    if task_id not in task_map:
        return None
    
    return task_map[task_id].to_response()

