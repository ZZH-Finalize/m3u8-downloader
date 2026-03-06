#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步后处理模块
使用 asyncio 异步调用 ffmpeg 合并分片
"""

import asyncio
import os
from pathlib import Path

from models import AppConfig, MergeResult
from logger import get_logger

logger = get_logger("postprocessor")


class MediaPostprocessor:
    """异步媒体后处理器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.output_file = config.output_file
        # 从环境变量或配置获取 ffmpeg 路径
        self.ffmpeg_path = os.environ.get("FFMPEG_PATH", config.ffmpeg_path)

    async def merge(self, segment_paths: list[Path]) -> MergeResult:
        """
        异步合并分片并转换为 mp4

        Args:
            segment_paths: 分片本地路径列表

        Returns:
            MergeResult: 合并结果
        """
        if not segment_paths:
            logger.error("没有可合并的分片")
            return MergeResult(
                success=False,
                error="没有可合并的分片"
            )

        # 检查 ffmpeg
        ffmpeg_available = await self._check_ffmpeg()
        if not ffmpeg_available:
            logger.error(f"未找到 ffmpeg，请确保已安装并添加到 PATH，或设置 FFMPEG_PATH 环境变量指定路径")
            return MergeResult(
                success=False,
                error="未找到 ffmpeg，请确保已安装并添加到 PATH，或设置 FFMPEG_PATH 环境变量指定路径"
            )

        # 创建临时文件列表
        temp_list_file = self._create_segment_list(segment_paths)

        # 执行 ffmpeg 合并
        logger.info(f"正在合并 {len(segment_paths)} 个分片并转换为 mp4...")

        success = await self._run_ffmpeg(temp_list_file)

        # 清理临时文件
        temp_list_file.unlink(missing_ok=True)

        if success:
            logger.info(f"合并完成：{self.output_file}")
            return MergeResult(
                success=True,
                output_path=self.output_file
            )
        else:
            logger.error("ffmpeg 执行失败")
            return MergeResult(
                success=False,
                error="ffmpeg 执行失败"
            )

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

    def _create_segment_list(
        self,
        segment_paths: list[Path]
    ) -> Path:
        """创建 ffmpeg 所需的文件列表"""
        temp_list_file = segment_paths[0].parent / "segments_list.txt"

        with open(temp_list_file, "w", encoding="utf-8") as f:
            for path in segment_paths:
                # 使用绝对路径，确保 ffmpeg 能正确找到文件
                abs_path = path.resolve()
                f.write(f"file '{abs_path.as_posix()}'\n")

        return temp_list_file

    async def _run_ffmpeg(self, list_file: Path) -> bool:
        """异步执行 ffmpeg 命令"""
        cmd = [
            self.ffmpeg_path,
            "-y",  # 覆盖输出文件
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",  # 直接复制流，不重新编码
            "-bsf:a", "aac_adtstoasc",  # 音频比特流过滤器
            self.output_file,
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

            logger.debug(f"ffmpeg 执行完成")
            return True
        except Exception as e:
            logger.error(f"ffmpeg 执行异常：{e}")
            return False
