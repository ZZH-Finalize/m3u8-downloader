import os
import shutil
import asyncio
import aiofiles
import config, task
from logger import get_logger

from models import Response, ErrorResponse, MetaData, CacheInfo, GetCacheResponse, ListCacheResponse
from typing import List

logger = get_logger(__name__)

async def get(cache_id: str) -> GetCacheResponse | ErrorResponse:
    cache_dir = config.server.cache_dir / cache_id

    if not cache_dir.exists():
        return ErrorResponse(status_code=404, msg=f'{cache_id} 不存在')

    async with aiofiles.open(cache_dir / config.server.metadata_file_name, 'r') as f:
        metadata = MetaData.model_validate_json(await f.read())
        return GetCacheResponse.model_validate({'id': cache_id, **metadata.model_dump()})

async def list() -> ListCacheResponse:
    caches: List[CacheInfo] = []

    for cache_id in os.listdir(config.server.cache_dir):
        metadata_file = config.server.cache_dir / cache_id / config.server.metadata_file_name

        if not metadata_file.exists():
            logger.warning(f'[{cache_id}] 缓存目录下没有元数据文件')
            continue

        async with aiofiles.open(metadata_file, 'r') as f:
            detail = MetaData.model_validate_json(await f.read())
            caches.append(CacheInfo(id=cache_id,
                                    url=detail.url,
                                    created_at=detail.created_at,
                                    segments_num=detail.segments_num))

    return ListCacheResponse(caches=caches, total_count=len(caches))


async def delete(cache_id: str) -> Response | ErrorResponse:
    if task.has(cache_id):
        return ErrorResponse(status_code=403, msg=f'{cache_id} 被任务占用, 拒绝删除')

    cache_dir = config.server.cache_dir / cache_id
    try:
        await asyncio.to_thread(shutil.rmtree, cache_dir)
    except Exception as e:
        logger.warning(f'[{cache_id}] 缓存删除失败\n{e}')
        return ErrorResponse(status_code=500, msg=f'{cache_id} 删除失败')

    return Response()

async def clear() -> Response:
    for cache_id in filter(lambda x: not task.has(x), os.listdir(config.server.cache_dir)):
        try:
            await asyncio.to_thread(shutil.rmtree, config.server.cache_dir / cache_id)
        except Exception as e:
            logger.warning(f'[{cache_id}] 缓存删除失败\n{e}')

    return Response()
