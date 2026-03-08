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


# 默认配置（可被 server.py 修改）
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "m3u8-downloader.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONSOLE_FORMAT = "[%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 存储已创建的 logger，避免重复创建
_loggers: dict[str, logging.Logger] = {}


def _create_handler_and_setup_logger(
    name: str,
    log_file: Path,
    level: int,
) -> logging.Logger:
    """创建并配置 logger 的通用逻辑"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 创建日志目录
    log_file.parent.mkdir(parents=True, exist_ok=True)

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
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(CONSOLE_FORMAT)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def setup_logger(
    name: str = "m3u8-downloader",
    level: int = logging.INFO,
    debug: bool = False,
) -> logging.Logger:
    """
    设置并返回日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        debug: 是否启用调试模式（DEBUG 级别）

    Returns:
        配置好的 Logger 实例
    """
    cache_key = f"{name}_{level}"
    if cache_key in _loggers:
        return _loggers[cache_key]

    log_level = logging.DEBUG if debug else level
    logger = _create_handler_and_setup_logger(name, LOG_FILE, log_level)

    # 缓存 logger
    _loggers[cache_key] = logger

    return logger


# 默认日志记录器
default_logger = setup_logger()


def get_logger(name: str = None, debug: bool = False) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 模块名称，默认使用默认记录器
        debug: 是否启用调试模式

    Returns:
        Logger 实例
    """
    if name is None:
        return default_logger

    log_level = logging.DEBUG if debug else logging.INFO
    cache_key = f"{name}_{log_level}"

    if cache_key in _loggers:
        return _loggers[cache_key]

    logger = _create_handler_and_setup_logger(name, LOG_FILE, log_level)
    _loggers[cache_key] = logger

    return logger
