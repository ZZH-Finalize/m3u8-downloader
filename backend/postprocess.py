import asyncio, os, shutil
import config

from models import TaskStatus
from task import DownloadTask
from logger import get_logger
from tempfile import NamedTemporaryFile

logger = get_logger(__name__)

async def clear_segments(task: DownloadTask):
    await asyncio.to_thread(shutil.rmtree, task.segments_dir)
    task.metadata.downloaded_mask.setall(0)

async def merge_segments(task: DownloadTask):
    if task.state == TaskStatus.PAUSED:
        logger.debug(f'[{task.id}] 任务暂停后处理, 等待恢复')
        await task.continue_evt.wait()

    task.state = TaskStatus.MERGING
    logger.info(f'[{task.id}] 开始后处理')

    f = NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8', prefix='zzh_')
    for segment in task.metadata.segments:
        segment_path = task.segments_dir / os.path.basename(segment)
        line = f'file \'{segment_path.resolve()}\'\n'
        logger.debug(f'[{task.id}] 写入 {line}')
        f.write(line)
    f.close()

    logger.debug(f'[{task.id}] 使用临时文件: {f.name}')

    cmd = ['ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', f.name,
            '-c', 'copy',
            # '-bsf:a', 'aac_adtstoasc',
            config.server.output_dir / task.output_name
        ]
    try:
        logger.debug(f'[{task.id}] 启动进程: {cmd}')
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
        raise
    finally:
        logger.debug(f'[{task.id}] 删除临时文件')
        os.remove(f.name)
        
