import aiofiles, asyncio
import config

from models import *
from logger import get_logger
from pathlib import Path

logger = get_logger(__name__)

class DownloadTask:

    @staticmethod
    def from_param(param: DownloadArgs):
        task_id = hash_func(param.url.encode('utf-8')).hexdigest()[:16]
        return DownloadTask(task_id, **param.model_dump(exclude={'queued',}))

    def __init__(self, id: str, url: str, threads: int, output_name: str,
                 output_encoding: OutputEncoding, max_rounds: int, 
                 max_retry: int, keep_cache: bool) -> None:
        self.id = id
        self.metadata = MetaData(url=url, base_url='')

        self.state = TaskStatus.PENDING
        self.threads = threads
        self.output_name = output_name
        self.output_encoding = output_encoding
        self.max_rounds = max_rounds
        self.max_retry = max_retry
        self.keep_cache = keep_cache

        self.worker: asyncio.Task | None = None

        self.old_state = TaskStatus.PENDING

        # 待下载分片 queue
        self.url_queue: asyncio.Queue[SegmentInfo | None] = asyncio.Queue()
        # 暂停控制
        self.continue_evt = asyncio.Event()
        # 完成控制
        self.complete = asyncio.Event()

        # 缓存路径
        self.cache_dir = config.server.cache_dir / self.id
        self.segments_dir = self.cache_dir / config.server.segments_dir
        self.metadata_file = self.cache_dir / config.server.metadata_file_name

        # 创建任务的cache路径
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.segments_dir.mkdir(parents=True, exist_ok=True)

    @property
    def url(self):
        return self.metadata.url

    def pause(self):
        if self.state not in (TaskStatus.PENDING, TaskStatus.PARSING, TaskStatus.DOWNLOADING):
            logger.warning(f'[{self.id}] 无法暂停, 因为当前状态: {self.state}')
            return

        logger.info(f'[{self.id}] 暂停执行')

        self.continue_evt.clear()
        self.old_state = self.state
        self.state = TaskStatus.PAUSED

    def resume(self):
        if self.state != TaskStatus.PAUSED:
            logger.warning(f'[{self.id}] 无法恢复, 因为当前状态: {self.state}')
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
            logger.debug(f'{self.metadata}')
        except Exception as e:
            logger.warning(f'[{self.id}] 元数据加载异常：{e}')
            raise

    async def cache_file(self, fn: Path | str, content, mode: str = 'w'):
        async with aiofiles.open(self.cache_dir / fn, mode) as f: # pyright: ignore[reportArgumentType, reportCallIssue]
            await f.write(content)

    async def flush_cache(self):
        await self.cache_file(config.server.metadata_file_name, self.metadata.model_dump_json())

    async def save_segment(self, fn: str, id: int, content):
        await self.cache_file(config.server.segments_dir / fn, content, mode='wb')
        self.metadata.downloaded_mask[id] = 1

    def to_response(self) -> GetTaskResponse:
        return GetTaskResponse(url=self.url,
                        task_id=self.id,
                        state=self.state,
                        segments_downloaded=self.metadata.downloaded_mask.count(),
                        total_segments=self.metadata.segments_num,
                        output_name=self.output_name)

from parser import parse_m3u8
from downloader import download_segments
from postprocess import merge_segments, clear_segments
from hashlib import md5 as hash_func

task_map: dict[str, DownloadTask] = {}
queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
current_queued_task: DownloadTask | None = None

concur_task_cnt: int = 0
concur_task_cnt_lock: asyncio.Lock = asyncio.Lock()

async def __exec(task: DownloadTask, queued: bool = False):
    global concur_task_cnt

    try:
        if False == queued:
            if concur_task_cnt == 0 and current_queued_task is not None:
                # 并发任务启动时, 暂停队列任务
                logger.info(f'并发任务[{task.id}]启动, 暂停队列任务 [{current_queued_task.id}]')
                current_queued_task.pause()

            async with concur_task_cnt_lock:
                concur_task_cnt += 1

        if task.cache_exists():
            logger.info(f'[{task.id}] 元数据文件存在')
            await task.load_cache()
        else:
            await parse_m3u8(task)

        await download_segments(task)
        await merge_segments(task)

        if False == task.keep_cache:
            logger.info(f'[{task.id}] 删除分片缓存')
            await clear_segments(task)
        else:
            logger.info(f'[{task.id}] 保留分片缓存')

        task.state = TaskStatus.COMPLETED

    except Exception as e:
        task.state = TaskStatus.FAILED
        logger.exception(f'[{task.id}] 任务出现异常: {e}')

    finally:
        logger.info(f'任务 [{task.id}] 停止')

        await task.flush_cache()

        if False == queued:
            async with concur_task_cnt_lock:
                concur_task_cnt -= 1

            if concur_task_cnt == 0 and current_queued_task is not None:
                # 并发任务结束后, 恢复队列任务
                current_queued_task.resume()
                logger.info(f'并发任务[{task.id}]停止, 恢复队列任务 [{current_queued_task.id}]')

async def queued_task_executor():
    global current_queued_task

    while True:
        task = await queue.get()

        logger.info(f'调度 [{task.id}] 进入执行')

        current_queued_task = task
        task.worker = asyncio.create_task(__exec(task, True))

        await asyncio.gather(task.worker)

        current_queued_task = None

async def add(param: DownloadArgs) -> DownloadResponse:
    task_id = hash_func(param.url.encode('utf-8')).hexdigest()[:16]

    if task_id in task_map:
        logger.info(f'任务[{task_id}]已存在')
        task = task_map[task_id]

        if task.state not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return DownloadResponse(task_id=task_id)
    else:
        logger.info(f'创建新任务: {task_id}')

        task = DownloadTask(task_id, **param.model_dump(exclude={'queued',}))

    logger.debug(f'任务信息:\n{param.model_dump_json(indent=4)}')

    if param.queued:
        logger.info(f'添加 [{task.id}] 到队列')
        await queue.put(task)
    else:
        logger.info(f'启动 [{task.id}] 并发执行')
        task.worker = asyncio.create_task(__exec(task))

    # 记录任务
    task_map[task_id] = task

    return DownloadResponse(task_id=task_id)

def id_not_exist(task_id: str) -> ErrorResponse:
    return ErrorResponse(status_code=404, msg=f'{task_id} 不存在')

def list() -> ListTaskResponse:
    tasks = []

    for task in task_map.values():
        tasks.append(task.to_response())

    return ListTaskResponse(tasks=tasks, total_count=len(tasks))

def get(task_id: str) -> GetTaskResponse | ErrorResponse:
    if task_id not in task_map:
        logger.info(f'任务 [{task_id}] 不存在')
        return id_not_exist(task_id)

    return task_map[task_id].to_response()

def pause(task_id: str) -> Response | ErrorResponse:
    logger.info(f'暂停任务 [{task_id}]')

    if task_id not in task_map:
       logger.info(f'任务 [{task_id}] 不存在')
       return id_not_exist(task_id)
    
    task_map[task_id].pause()

    return Response()

def resume(task_id: str) -> Response | ErrorResponse:
    logger.info(f'恢复任务 [{task_id}]')

    if task_id not in task_map:
        logger.info(f'任务 [{task_id}] 不存在')
        return id_not_exist(task_id)

    task_map[task_id].resume()

    return Response()

def delete(task_id: str) -> Response | ErrorResponse:
    logger.info(f'删除任务 [{task_id}]')

    if task_id not in task_map:
        logger.info(f'任务 [{task_id}] 不存在')
        return id_not_exist(task_id)

    worker = task_map[task_id].worker
    if worker is not None:
        logger.debug(f'[{task_id}] worker停止')
        worker.cancel()

    task_map.pop(task_id)

    return Response()

def has(task_id: str) -> bool:
    return task_id in task_map
