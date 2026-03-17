#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志模块
配置 logging，同时输出到控制台和文件
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from config import ServerConfig

# 默认配置
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONSOLE_FORMAT = "[%(name)s][%(levelname)s]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(config: ServerConfig) -> logging.Logger:
    """
    设置并返回日志记录器

    Args:
        config: 服务器配置

    Returns:
        配置好的 Logger 实例
    """

    log_dir = config.log_dir
    log_file = log_dir / "m3u8-downloader.log"
    log_level = logging.DEBUG if config.debug else config.log_level

    logger = logging.getLogger("m3u8-downloader")
    if logger.handlers:
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    # 创建日志目录
    log_dir.mkdir(parents=True, exist_ok=True)

    # 文件处理器 - 轮转文件，最大 10MB，保留 5 个文件
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
        mode='w'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(CONSOLE_FORMAT)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 模块名称，默认使用默认记录器

    Returns:
        Logger 实例
    """
    if name is None:
        return logging.getLogger("m3u8-downloader")
    return logging.getLogger(f"m3u8-downloader.{name}")
