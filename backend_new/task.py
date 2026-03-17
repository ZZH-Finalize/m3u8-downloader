from models import CacheInfo, MetaData
from config import server_config as config
from logger import get_logger
import aiofiles

logger = get_logger('task')

METADATA_FILE_NAME = 'metadata.json'

class DownloadTask:
    def __init__(self, url: str) -> None:
        self.cache = CacheInfo(metadata=MetaData(url=url))
        self.__cache_dir = config.temp_dir / self.cache.id
        self.__metadata_file = self.__cache_dir / METADATA_FILE_NAME

    @property
    def metadata(self):
        return self.cache.metadata

    @property
    def url(self):
        return self.cache.metadata.url

    @property
    def id(self):
        return self.cache.id
    
    def cache_exists(self):
        return self.__metadata_file.exists()

    async def save_tmp_file(self, fn: str, content: str):
        async with aiofiles.open(self.__cache_dir / fn, 'w') as f:
            await f.write(content)
        logger.debug(f'[{self.id}] cache file: {fn}')

    async def load_cache(self):
        try:
            async with aiofiles.open(self.__metadata_file, 'r') as f:
                metadata = await f.read()

            self.cache.metadata.model_validate_json(metadata)
        except Exception as e:
            logger.warning(f'[{self.id}] metadata load fail: {e.with_traceback(e.__traceback__)}')

    async def clear_segments(self):
        pass
