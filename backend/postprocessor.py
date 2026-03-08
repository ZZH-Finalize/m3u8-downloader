#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步后处理模块
使用 asyncio 异步调用 ffmpeg 合并分片
"""

import asyncio
import tempfile
from pathlib import Path

from models import AppConfig, MergeResult
from logger import get_logger

logger = get_logger("postprocessor")


class MediaPostprocessor:
    """异步媒体后处理器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.output_file = config.output_file
        self.ffmpeg_path = config.ffmpeg_path

    async def merge(self, segment_paths: list[Path]) -> MergeResult:
        """
        异步合并分片并转换为 mp4

        Args:
            segment_paths: 分片本地路径列表（已按 metadata.filenames 顺序排列）

        Returns:
            MergeResult: 合并结果
        """
        if not segment_paths:
            logger.error("没有可合并的分片")
            return MergeResult(success=False, error="没有可合并的分片")

        if not await self._check_ffmpeg():
            error_msg = "未找到 ffmpeg，请确保已安装并添加到 PATH，或设置 FFMPEG_PATH 环境变量指定路径"
            logger.error(error_msg)
            return MergeResult(success=False, error=error_msg)

        project_root = Path(__file__).resolve().parent.parent
        temp_list_file = self._create_ffmpeg_list_file(segment_paths)

        logger.info(f"正在合并 {len(segment_paths)} 个分片并转换为 mp4...")
        success = await self._run_ffmpeg(temp_list_file, project_root)

        temp_list_file.unlink(missing_ok=True)

        if success:
            logger.info(f"合并完成：{self.output_file}")
            return MergeResult(success=True, output_path=self.output_file)
        else:
            logger.error("ffmpeg 执行失败")
            return MergeResult(success=False, error="ffmpeg 执行失败")

    async def _check_ffmpeg(self) -> bool:
        """异步检查 ffmpeg 是否可用"""
        try:
            process = await asyncio.create_subprocess_exec(
                self.ffmpeg_path, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except (FileNotFoundError, Exception):
            return False

    def _create_ffmpeg_list_file(self, segment_paths: list[Path]) -> Path:
        """
        创建 ffmpeg 所需的文件列表（使用系统临时目录）

        Args:
            segment_paths: 分片路径列表

        Returns:
            临时文件路径
        """
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            prefix="m3u8_ffmpeg_",
            delete=False,
            encoding="utf-8"
        )

        with temp_file:
            for path in segment_paths:
                temp_file.write(f"file '{path.resolve()}'\n")

        return Path(temp_file.name)

    async def _run_ffmpeg(self, list_file: Path, work_dir: Path) -> bool:
        """
        异步执行 ffmpeg 命令

        Args:
            list_file: 分片列表文件路径（系统临时目录）
            work_dir: 工作目录（ffmpeg 运行目录）
        """
        output_path = Path(self.output_file).resolve()

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            str(output_path),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""
                logger.error(f"ffmpeg 执行失败：{stderr_str}")
                return False

            logger.debug("ffmpeg 执行完成")
            return True
        except Exception as e:
            logger.error(f"ffmpeg 执行异常：{e}")
            return False
