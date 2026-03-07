#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务管理模块
管理后台下载任务，分离前台 API 响应与后台任务执行
"""

import asyncio
import os
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field

from models import AppConfig, ParseResult, DownloadResult, MergeResult
from parser import M3u8Parser
from downloader import SegmentDownloader
from postprocessor import MediaPostprocessor
from cache_manager import CacheManager
from logger import get_logger

logger = get_logger("task_manager")


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待中
    PARSING = "parsing"           # 解析中
    DOWNLOADING = "downloading"   # 下载中
    MERGING = "merging"           # 合并中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


@dataclass
class TaskProgress:
    """任务进度信息"""
    status: TaskStatus = TaskStatus.PENDING
    progress_percent: float = 0.0  # 进度百分比 (0-100)
    current_step: str = ""         # 当前步骤描述
    segments_downloaded: int = 0   # 已下载分片数
    total_segments: int = 0        # 总分片数
    error: Optional[str] = None    # 错误信息
    result: Optional[dict] = None  # 最终结果
    created_at: str = ""           # 创建时间
    started_at: Optional[str] = None  # 开始时间
    completed_at: Optional[str] = None  # 完成时间

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "status": self.status.value,
            "progress_percent": round(self.progress_percent, 2),
            "current_step": self.current_step,
            "segments_downloaded": self.segments_downloaded,
            "total_segments": self.total_segments,
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


@dataclass
class DownloadTask:
    """下载任务"""
    task_id: str
    config: AppConfig
    progress: TaskProgress = field(default_factory=TaskProgress)
    _cancel_flag: bool = False

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "url": self.config.url,
            "progress": self.progress.to_dict()
        }


class TaskManager:
    """
    任务管理器
    负责创建、跟踪和管理后台下载任务
    """

    def __init__(self):
        self._tasks: Dict[str, DownloadTask] = {}
        self._task_futures: Dict[str, asyncio.Task] = {}

    def find_task_by_url(self, url: str) -> Optional[DownloadTask]:
        """
        根据 URL 查找任务

        Args:
            url: m3u8 URL

        Returns:
            匹配的任务，如果不存在则返回 None
        """
        for task in self._tasks.values():
            if task.config.url == url:
                return task
        return None

    def create_task(
        self,
        url: str,
        threads: int = 8,
        output_dir: str = "output",
        temp_dir: str = "temp_segments",
        max_rounds: int = 5,
        keep_cache: bool = False,
        output_name: str = None
    ) -> DownloadTask:
        """
        创建新的下载任务

        Args:
            url: m3u8 URL
            threads: 并发线程数
            output_dir: 输出目录
            temp_dir: 临时目录
            max_rounds: 最大下载轮次
            keep_cache: 是否保留缓存
            output_name: 输出文件名

        Returns:
            DownloadTask: 任务对象
        """
        task_id = str(uuid.uuid4())[:8]

        # 创建配置
        config = AppConfig(
            url=url,
            threads=threads,
            temp_dir=temp_dir,
            output_dir=output_dir,
            max_download_rounds=max_rounds,
            keep_cache=keep_cache,
            ffmpeg_path=os.environ.get("FFMPEG_PATH", "ffmpeg"),
        )

        # 创建缓存管理器
        cache_manager = CacheManager(
            temp_dir=config.temp_dir,
            url=config.url,
            keep_cache=config.keep_cache
        )

        # 设置输出文件路径
        output_name = output_name or "video.mp4"
        output_path = Path(config.output_dir) / cache_manager.cache_path.name / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        config.output_file = str(output_path)

        # 创建任务
        task = DownloadTask(
            task_id=task_id,
            config=config,
            progress=TaskProgress()
        )

        self._tasks[task_id] = task
        logger.info(f"创建任务：{task_id}, URL={url}")

        return task

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        if task:
            return {
                "success": True,
                "task_id": task_id,
                "url": task.config.url,
                "progress": task.progress.to_dict()
            }
        return None

    def list_tasks(self) -> list:
        """列出所有任务"""
        return [
            {
                "task_id": task.task_id,
                "url": task.config.url,
                "progress": task.progress.to_dict()
            }
            for task in self._tasks.values()
        ]

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.progress.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.warning(f"任务 {task_id} 已结束，无法取消")
            return False

        task._cancel_flag = True
        task.progress.status = TaskStatus.CANCELLED
        task.progress.completed_at = datetime.now().isoformat()
        task.progress.error = "用户取消"

        # 取消对应的 future
        if task_id in self._task_futures:
            self._task_futures[task_id].cancel()

        logger.info(f"任务已取消：{task_id}")
        return True

    def remove_task(self, task_id: str) -> bool:
        """
        移除任务（从任务列表中删除）
        仅当任务已结束（完成、失败或取消）时才能移除

        Args:
            task_id: 任务 ID

        Returns:
            是否成功移除
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        # 检查任务是否已结束
        if task.progress.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.warning(f"任务 {task_id} 仍在运行中，无法移除")
            return False
        
        if task_id in self._tasks:
            del self._tasks[task_id]
            if task_id in self._task_futures:
                del self._task_futures[task_id]
            logger.info(f"任务已移除：{task_id}")
            return True
        return False

    async def execute_task(self, task: DownloadTask) -> dict:
        """
        执行下载任务（异步）

        Args:
            task: 任务对象

        Returns:
            执行结果
        """
        task_id = task.task_id
        config = task.config
        progress = task.progress

        try:
            # 更新状态
            progress.started_at = datetime.now().isoformat()
            progress.status = TaskStatus.PARSING
            progress.current_step = "解析 m3u8..."

            logger.info(f"开始执行任务：{task_id}")

            # 创建缓存管理器
            cache_manager = CacheManager(
                temp_dir=config.temp_dir,
                url=config.url,
                keep_cache=config.keep_cache
            )

            # 1. 解析 m3u8
            logger.info(f"[{task_id}] 开始解析 m3u8...")
            parser = M3u8Parser(config, cache_manager)
            parse_result = await parser.parse()

            if task._cancel_flag:
                return self._create_cancelled_result(task)

            if not parse_result.success:
                raise Exception(f"解析失败：{parse_result.error}")

            config.parsed_segments = parse_result.segments
            config.metadata = cache_manager.load_metadata()
            logger.info(f"[{task_id}] 解析成功，共 {len(config.parsed_segments)} 个分片")

            # 更新进度
            progress.total_segments = len(config.parsed_segments)
            progress.progress_percent = 10.0

            # 2. 下载分片
            logger.info(f"[{task_id}] 开始下载分片...")
            progress.status = TaskStatus.DOWNLOADING
            progress.current_step = "下载分片中..."

            # 定义进度回调函数
            def on_progress(completed: int, total: int):
                progress.segments_downloaded = completed
                progress.progress_percent = 10.0 + (70.0 * completed / total)  # 10% -> 80%
                logger.debug(f"[{task_id}] 下载进度：{completed}/{total} ({progress.progress_percent:.1f}%)")

            downloader = SegmentDownloader(config, cache_manager, progress_callback=on_progress)
            download_results = await downloader.download_all(config.parsed_segments)

            if task._cancel_flag:
                return self._create_cancelled_result(task)

            # 统计结果
            success_count = sum(1 for r in download_results if r.success)
            failed_count = sum(1 for r in download_results if not r.success)

            if failed_count > 0:
                logger.warning(f"[{task_id}] {failed_count} 个分片下载失败")

            if success_count == 0:
                raise Exception("没有成功下载任何分片")

            logger.info(f"[{task_id}] 下载完成：{success_count}/{len(config.parsed_segments)} 个分片")

            # 检查是否所有分片都下载成功
            if failed_count > 0:
                # 分片未全部下载成功，标记任务失败，保留现有分片
                error_msg = f"分片未全部下载成功：{failed_count}/{len(config.parsed_segments)} 个失败"
                logger.error(f"[{task_id}] {error_msg}，任务失败，保留已下载分片")
                raise Exception(error_msg)

            # 保存下载路径
            config.downloaded_paths = downloader.get_success_paths(download_results)

            # 更新进度
            progress.segments_downloaded = success_count
            progress.progress_percent = 80.0

            # 3. 合并分片
            logger.info(f"[{task_id}] 开始合并分片...")
            progress.status = TaskStatus.MERGING
            progress.current_step = "合并分片中..."

            postprocessor = MediaPostprocessor(config)
            merge_result = await postprocessor.merge(config.downloaded_paths)

            if task._cancel_flag:
                return self._create_cancelled_result(task)

            if not merge_result.success:
                raise Exception(f"合并失败：{merge_result.error}")

            # 合并成功后清理分片文件
            cache_manager.clear_segments()

            # 更新进度
            progress.status = TaskStatus.COMPLETED
            progress.progress_percent = 100.0
            progress.current_step = "完成"
            progress.completed_at = datetime.now().isoformat()

            result = {
                "success": True,
                "output_path": config.output_file,
                "segments_downloaded": success_count,
                "total_segments": len(config.parsed_segments)
            }
            progress.result = result

            logger.info(f"[{task_id}] 任务完成，输出文件：{config.output_file}")
            return result

        except asyncio.CancelledError:
            logger.info(f"任务被取消：{task_id}")
            return self._create_cancelled_result(task)

        except Exception as e:
            logger.error(f"[{task_id}] 任务失败：{e}")
            progress.status = TaskStatus.FAILED
            progress.error = str(e)
            progress.completed_at = datetime.now().isoformat()

            return {
                "success": False,
                "error": str(e)
            }

    def start_task(self, task_id: str) -> bool:
        """
        启动后台任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功启动
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        # 获取当前运行的事件循环（而不是使用预先设置的 loop）
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.error("没有正在运行的事件循环")
            return False

        # 创建协程任务
        future = loop.create_task(self.execute_task(task))
        self._task_futures[task_id] = future

        logger.info(f"任务 {task_id} 已在事件循环中启动")
        return True

    def _create_cancelled_result(self, task: DownloadTask) -> dict:
        """创建取消结果"""
        return {
            "success": False,
            "error": "任务已取消",
            "cancelled": True
        }


# 全局任务管理器实例
task_manager = TaskManager()
