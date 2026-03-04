#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后处理模块
负责调用 ffmpeg 合并分片并转换为 mp4
"""

import subprocess
from pathlib import Path

from models import AppConfig, MergeResult
from logger import get_logger

logger = get_logger("postprocessor")


class MediaPostprocessor:
    """媒体后处理器"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.output_file = config.output_file
    
    def merge(self, segment_paths: list[Path]) -> MergeResult:
        """
        合并分片并转换为 mp4
        
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
        if not self._check_ffmpeg():
            logger.error("未找到 ffmpeg，请确保已安装并添加到 PATH")
            return MergeResult(
                success=False,
                error="未找到 ffmpeg，请确保已安装并添加到 PATH"
            )
        
        # 创建临时文件列表
        temp_list_file = self._create_segment_list(segment_paths)
        
        # 执行 ffmpeg 合并
        logger.info(f"正在合并 {len(segment_paths)} 个分片并转换为 mp4...")
        
        success = self._run_ffmpeg(temp_list_file)
        
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
    
    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _create_segment_list(
        self,
        segment_paths: list[Path]
    ) -> Path:
        """
        创建 ffmpeg 所需的文件列表

        Args:
            segment_paths: 分片路径列表

        Returns:
            临时列表文件路径
        """
        temp_list_file = segment_paths[0].parent / "segments_list.txt"

        with open(temp_list_file, "w", encoding="utf-8") as f:
            for path in segment_paths:
                # 使用绝对路径，确保 ffmpeg 能正确找到文件
                abs_path = path.resolve()
                f.write(f"file '{abs_path.as_posix()}'\n")

        return temp_list_file
    
    def _run_ffmpeg(self, list_file: Path) -> bool:
        """
        执行 ffmpeg 命令
        
        Args:
            list_file: 分片列表文件路径
            
        Returns:
            是否成功
        """
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖输出文件
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",  # 直接复制流，不重新编码
            "-bsf:a", "aac_adtstoasc",  # 音频比特流过滤器
            self.output_file,
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True, 
                text=True
            )
            logger.debug(f"ffmpeg 输出：{result.stderr}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg 执行失败：{e.stderr}")
            return False
