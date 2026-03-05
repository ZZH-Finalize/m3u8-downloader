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
_loggers = {}


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
    # 如果已经创建过且不需要重新配置，直接返回
    cache_key = f"{name}_{level}"
    if cache_key in _loggers:
        return _loggers[cache_key]
    
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 设置日志级别
    log_level = logging.DEBUG if debug else level
    logger.setLevel(log_level)

    # 创建日志目录
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 文件处理器 - 轮转文件，最大 10MB，保留 5 个文件
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(CONSOLE_FORMAT)
    console_handler.setFormatter(console_formatter)

    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
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
    
    # 获取当前全局的 LOG_FILE
    log_file = LOG_FILE
    log_level = logging.DEBUG if debug else logging.INFO
    
    # 检查是否需要为该 name 创建新的 logger
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 创建新的 logger
        logger.setLevel(log_level)
        
        # 文件处理器
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
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
