import aiofiles, asyncio, aiohttp

from models import CacheInfo, MetaData, SegmentInfo
from config import server_config as config
from logger import get_logger
from pathlib import Path

logger = get_logger(__name__)

METADATA_FILE_NAME = 'metadata.json'

class DownloadTask:
    def __init__(self, url: str, max_threads: int, output_name: str) -> None:
        self.cache = CacheInfo(metadata=MetaData(url=url, base_url=''))

        self.cache.metadata.output_name = output_name
        self.max_threads = max_threads

        # 待下载分片queue
        self.url_queue: asyncio.Queue[SegmentInfo | None] = asyncio.Queue()
        # 暂停控制
        self.continue_evt = asyncio.Event()
        # 完成控制
        self.complete = asyncio.Event()

        # 缓存路径
        self.cache_dir = config.temp_dir / self.cache.id
        self.segments_dir = self.cache_dir / 'segments'
        self.metadata_file = self.cache_dir / METADATA_FILE_NAME

        # 创建任务的cache路径
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.segments_dir.mkdir(parents=True, exist_ok=True)

    @property
    def id(self):
        return self.cache.id

    @property
    def metadata(self):
        return self.cache.metadata

    @property
    def url(self):
        return self.cache.metadata.url

    @property
    def state(self):
        return self.cache.metadata.state

    @state.setter
    def state(self, state):
        self.cache.metadata.state = state
    
    def cache_exists(self):
        return self.metadata_file.exists()

    async def load_cache(self):
        try:
            async with aiofiles.open(self.metadata_file, 'r') as f:
                metadata = await f.read()

            self.cache.metadata = MetaData.model_validate_json(metadata)
            logger.info(f'[{self.id}] 载入元数据')
        except Exception as e:
            logger.warning(f'[{self.id}] 元数据加载异常: {e}')
            raise

    async def cache_file(self, fn: Path | str, content, mode: str = 'w'):
        async with aiofiles.open(self.cache_dir / fn, mode) as f: # pyright: ignore[reportArgumentType, reportCallIssue]
            await f.write(content)

    async def flush_cache(self):
        await self.cache_file(METADATA_FILE_NAME, self.cache.metadata.model_dump_json())

    async def save_segment(self, fn: str, id: int, content):
        await self.cache_file(Path('segments') / fn, content, mode='wb')
        self.metadata.downloaded_mask[id] = 1

    async def clear_segments(self):
        pass
