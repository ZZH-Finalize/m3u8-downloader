import asyncio, os
import config

from models import TaskStatus
from task import DownloadTask
from logger import get_logger
from tempfile import NamedTemporaryFile

logger = get_logger(__name__)

async def merge_segments(task: DownloadTask):
    task.state = TaskStatus.MERGING
    logger.info(f'[{task.id}] 开始后处理')

    f = NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8', prefix='zzh_')
    for segment in task.metadata.segments:
        segment_path = task.segments_dir / os.path.basename(segment)
        line = f'file \'{segment_path.resolve()}\'\n'
        logger.debug(f'[{task.id}] 写入 {line}')
        f.write(line)
    f.close()

    cmd = ['ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', f.name,
            '-c', 'copy',
            # '-bsf:a', 'aac_adtstoasc',
            config.server_config.output_dir / task.metadata.output_name
        ]
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ''
            logger.error(f'[{task.id}] ffmpeg 执行失败：{stderr_str}')
            return

        logger.info(f'[{task.id}] ffmpeg 执行完成')
    except Exception as e:
        logger.error(f'[{task.id}] ffmpeg 执行异常：{e}')
    finally:
        logger.debug(f'[{task.id}] 删除临时文件')
        os.remove(f.name)
        
