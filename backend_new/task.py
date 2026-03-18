import aiofiles, asyncio, aiohttp

from models import CacheInfo, MetaData, SegmentInfo
from config import server_config as config
from logger import get_logger

logger = get_logger('task')

METADATA_FILE_NAME = 'metadata.json'

class DownloadTask:
    def __init__(self, url: str, output_name: str) -> None:
        self.cache = CacheInfo(metadata=MetaData(url=url))
        self.cache.metadata.output_name = output_name
        self.base_url = ''
        self.__cache_dir = config.temp_dir / self.cache.id
        self.__metadata_file = self.__cache_dir / METADATA_FILE_NAME

        # 待下载分片queue
        self.url_queue: asyncio.Queue[SegmentInfo | None] = asyncio.Queue()
        # 暂停控制
        self.continue_evt = asyncio.Event()
        # 完成控制
        self.complete = asyncio.Event()
        # 协程池
        self.task_pool = []

        # http会话
        self.session: aiohttp.ClientSession | None = None

        # 创建任务的cache路径
        cache_dir = config.temp_dir / self.cache.id
        cache_dir.mkdir(parents=True, exist_ok=True)

        segments_dir = cache_dir / 'segments'
        segments_dir.mkdir(parents=True, exist_ok=True)

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
        return self.__metadata_file.exists()

    async def save_tmp_file(self, fn: str, content: str):
        async with aiofiles.open(self.__cache_dir / fn, 'w') as f:
            await f.write(content)
        logger.debug(f'[{self.id}] cache 命中: {fn}')

    async def load_cache(self):
        try:
            async with aiofiles.open(self.__metadata_file, 'r') as f:
                metadata = await f.read()

            self.cache.metadata = MetaData.model_validate_json(metadata)
            logger.info(f'[{self.id}] 载入元数据')
        except Exception as e:
            logger.warning(f'[{self.id}] 元数据加载异常: {e.with_traceback(e.__traceback__)}')
            raise

    async def clear_segments(self):
        pass
