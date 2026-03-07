#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 下载服务 - 异步后端 API 服务

架构说明:
- 使用 Quart 异步框架 (Flask 的异步版本)
- 前台任务：响应 API 请求（立即返回）
- 后台任务：下载分片、转码等（异步执行）
- 任务管理器：跟踪和管理所有后台任务
"""

import sys
import argparse
import logging
import os
from pathlib import Path
from typing import Optional

# 添加当前目录到路径，确保模块导入正确
sys.path.insert(0, str(Path(__file__).parent))

from quart import Quart, request, jsonify
from quart_cors import cors
import asyncio

from models import AppConfig
from cache_manager import CacheManager
from task_manager import task_manager, TaskManager, TaskStatus
from logger import get_logger, LOG_FILE, setup_logger

# 全局配置
server_config = {
    "default_threads": 8,  # 默认下载并发数
    "ffmpeg_path": os.environ.get("FFMPEG_PATH", "ffmpeg"),  # ffmpeg 路径
}

logger = None  # 在 main() 中初始化

app = Quart(__name__)
app = cors(app)  # 启用 CORS 支持


# ===== API 端点 =====

@app.route('/health', methods=['GET'])
async def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "service": "m3u8-downloader-api",
        "async": True
    })


@app.route('/api/config', methods=['GET'])
async def get_server_config():
    """获取服务器配置信息"""
    return jsonify({
        "default_threads": server_config.get("default_threads", 8),
        "log_level": logging.getLevelName(logger.level),
        "log_dir": str(LOG_FILE.parent)
    })


@app.route('/api/download', methods=['POST'])
async def download():
    """
    提交下载任务（异步）

    请求体:
    {
        "url": "https://example.com/video.m3u8",
        "threads": 4,          // 可选，默认使用服务器配置的 default_threads
        "output": "video.mp4",  // 可选，默认 video.mp4
        "max_rounds": 5,        // 可选，默认 5
        "keep_cache": false,    // 可选，默认 false
        "debug": false          // 可选，默认 false
    }

    返回:
    {
        "success": true,
        "task_id": "abc12345",  // 任务 ID，用于查询进度
        "status": "pending"
    }
    """
    global logger

    try:
        data = await request.get_json()

        if not data or 'url' not in data:
            return jsonify({
                "success": False,
                "error": "缺少必要参数：url"
            }), 400

        url = data['url']
        threads = data.get('threads')
        output_name = data.get('output')
        max_rounds = data.get('max_rounds', 5)
        keep_cache = data.get('keep_cache', False)
        debug = data.get('debug', False)

        # 验证参数
        if threads is not None and threads < 1:
            return jsonify({
                "success": False,
                "error": "线程数必须大于 0"
            }), 400

        # 启用调试模式
        if debug:
            get_logger("api_server", debug=True)
            get_logger("parser", debug=True)
            get_logger("downloader", debug=True)
            get_logger("postprocessor", debug=True)

        logger.info(f"收到下载请求：URL={url}")

        # 检查是否存在相同 URL 的任务
        existing_task = task_manager.find_task_by_url(url)

        if existing_task:
            # 任务已存在
            if existing_task.progress.status == TaskStatus.FAILED:
                # 失败任务：重新启动
                logger.info(f"发现失败任务 {existing_task.task_id}，重新启动")
                # 重置任务状态
                existing_task.progress.status = TaskStatus.PENDING
                existing_task.progress.error = None
                existing_task.progress.progress_percent = 0.0
                existing_task.progress.current_step = "等待重启"
                existing_task._cancel_flag = False
                # 启动任务
                task_manager.start_task(existing_task.task_id)
                return jsonify({
                    "success": True,
                    "task_id": existing_task.task_id,
                    "status": "pending",
                    "message": "失败任务已重启"
                })
            elif existing_task.progress.status in [TaskStatus.PENDING, TaskStatus.PARSING, TaskStatus.DOWNLOADING, TaskStatus.MERGING]:
                # 运行中任务
                logger.info(f"任务已存在且正在运行：{existing_task.task_id}, 状态={existing_task.progress.status}")
                return jsonify({
                    "success": False,
                    "error": f"任务已存在且正在运行：{existing_task.task_id}",
                    "existing_task_id": existing_task.task_id,
                    "existing_status": existing_task.progress.status.value
                }), 409
            else:
                # 已完成或已取消
                logger.info(f"任务已存在：{existing_task.task_id}, 状态={existing_task.progress.status}")
                return jsonify({
                    "success": False,
                    "error": f"任务已存在：{existing_task.task_id}",
                    "existing_task_id": existing_task.task_id,
                    "existing_status": existing_task.progress.status.value
                }), 409

        # 创建新任务
        task = task_manager.create_task(
            url=url,
            threads=threads if threads is not None else server_config.get("default_threads", 8),
            output_dir="output",
            temp_dir="temp_segments",
            max_rounds=max_rounds,
            keep_cache=keep_cache,
            output_name=output_name
        )

        # 启动后台任务
        task_manager.start_task(task.task_id)

        logger.info(f"任务已创建：{task.task_id}")

        # 立即返回任务 ID，不等待下载完成
        return jsonify({
            "success": True,
            "task_id": task.task_id,
            "status": "pending",
            "message": "任务已提交，后台执行中"
        })

    except Exception as e:
        logger.error(f"处理下载请求时发生错误：{e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/download/sync', methods=['POST'])
async def download_sync():
    """
    同步下载（等待完成）- 用于兼容旧 API

    请求体与 /api/download 相同

    返回:
    {
        "success": true/false,
        "output_path": "...",
        "segments_downloaded": 100,
        "total_segments": 100,
        "error": "..."
    }
    """
    try:
        data = await request.get_json()

        if not data or 'url' not in data:
            return jsonify({
                "success": False,
                "error": "缺少必要参数：url"
            }), 400

        url = data['url']
        threads = data.get('threads')
        output_name = data.get('output')
        max_rounds = data.get('max_rounds', 5)
        keep_cache = data.get('keep_cache', False)

        logger.info(f"收到同步下载请求：URL={url}")

        # 创建任务
        task = task_manager.create_task(
            url=url,
            threads=threads if threads is not None else server_config.get("default_threads", 8),
            output_dir="output",
            temp_dir="temp_segments",
            max_rounds=max_rounds,
            keep_cache=keep_cache,
            output_name=output_name
        )

        # 等待任务完成
        result = await task_manager.execute_task(task)

        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 500 if not result.get("cancelled") else 400

    except Exception as e:
        logger.error(f"处理同步下载请求时发生错误：{e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/tasks', methods=['GET'])
async def list_tasks():
    """列出所有任务"""
    tasks = task_manager.list_tasks()
    return jsonify({
        "success": True,
        "tasks": tasks,
        "total_count": len(tasks)
    })


@app.route('/api/task/list', methods=['GET'])
async def list_task_ids():
    """
    列出所有任务 ID 及下载进度
    
    返回:
    {
        "success": true,
        "tasks": [
            {
                "task_id": "abc12345",
                "segments_downloaded": 45,
                "total_segments": 100
            },
            ...
        ],
        "total_count": 2
    }
    """
    tasks = task_manager.list_tasks()
    
    # 提取精简信息
    task_list = [
        {
            "task_id": task["task_id"],
            "segments_downloaded": task["progress"].get("segments_downloaded", 0),
            "total_segments": task["progress"].get("total_segments", 0)
        }
        for task in tasks
    ]
    
    return jsonify({
        "success": True,
        "tasks": task_list,
        "total_count": len(task_list)
    })


@app.route('/api/tasks/<task_id>', methods=['GET'])
async def get_task_status(task_id: str):
    """获取任务状态"""
    result = task_manager.get_task_status(task_id)

    if result:
        return jsonify(result)
    else:
        return jsonify({
            "success": False,
            "error": "任务不存在"
        }), 404


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
async def delete_task(task_id: str):
    """
    删除任务
    - 如果任务正在运行：先取消任务，再从列表中移除
    - 如果任务已结束（完成/失败/取消）：直接从列表中移除
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": "任务不存在"
        }), 404
    
    # 如果任务正在运行，先取消
    if task.progress.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        task_manager.cancel_task(task_id)
    
    # 移除任务
    task_manager.remove_task(task_id)
    
    return jsonify({
        "success": True,
        "message": f"任务已删除：{task_id}"
    })


# ===== 缓存管理 API =====

@app.route('/api/cache/list', methods=['GET'])
async def cache_list():
    """
    列出所有缓存
    """
    temp_dir = Path("temp_segments")

    if not temp_dir.exists():
        return jsonify({
            "success": True,
            "caches": [],
            "total_count": 0
        })

    cache_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
    caches = []

    for cache_dir in cache_dirs:
        cache_manager = CacheManager(
            temp_dir=str(temp_dir),
            url="",
            keep_cache=True
        )
        cache_manager.cache_dir = cache_dir

        cache_info = cache_manager.get_cache_info()
        metadata = cache_manager.load_metadata()

        cache_data = {
            "id": cache_dir.name,
            "url": metadata.url if metadata else "未知",
            "segment_count": cache_info["segment_count"],
            "m3u8_count": cache_info["m3u8_count"],
            "total_size": cache_info["total_size"],
            "total_size_mb": round(cache_info["total_size"] / (1024 * 1024), 2),
            "created_at": metadata.created_at if metadata else None
        }
        caches.append(cache_data)

    return jsonify({
        "success": True,
        "caches": caches,
        "total_count": len(caches)
    })


@app.route('/api/cache/<cache_id>', methods=['GET'])
async def cache_get(cache_id: str):
    """获取指定缓存的详细信息"""
    temp_dir = Path("temp_segments")
    cache_dir = temp_dir / cache_id

    if not cache_dir.exists():
        return jsonify({
            "success": False,
            "error": f"缓存不存在：{cache_id}"
        }), 404

    cache_manager_instance = CacheManager(
        temp_dir=str(temp_dir),
        url="",
        keep_cache=True
    )
    cache_manager_instance.cache_dir = cache_dir

    cache_info = cache_manager_instance.get_cache_info()
    metadata = cache_manager_instance.load_metadata()

    downloaded_count = 0
    is_complete = False
    if metadata:
        downloaded_count = bin(metadata.downloaded_mask).count("1")
        is_complete = metadata.is_complete

    return jsonify({
        "success": True,
        "cache": {
            "id": cache_id,
            "url": metadata.url if metadata else "未知",
            "base_url": metadata.base_url if metadata else None,
            "segment_count": cache_info["segment_count"],
            "m3u8_count": cache_info["m3u8_count"],
            "total_size": cache_info["total_size"],
            "total_size_mb": round(cache_info["total_size"] / (1024 * 1024), 2),
            "created_at": metadata.created_at if metadata else None,
            "downloaded_count": downloaded_count,
            "is_complete": is_complete
        }
    })


@app.route('/api/cache/<cache_id>', methods=['DELETE'])
async def cache_delete(cache_id: str):
    """删除指定缓存"""
    temp_dir = Path("temp_segments")
    cache_dir = temp_dir / cache_id

    if not cache_dir.exists():
        return jsonify({
            "success": False,
            "error": f"缓存不存在：{cache_id}"
        }), 404

    cache_manager_instance = CacheManager(
        temp_dir=str(temp_dir),
        url="",
        keep_cache=False
    )
    cache_manager_instance.cache_dir = cache_dir

    success = cache_manager_instance.clear_cache()

    if success:
        return jsonify({
            "success": True,
            "message": f"缓存已删除：{cache_id}"
        })
    else:
        return jsonify({
            "success": False,
            "error": f"删除失败：{cache_id}"
        }), 500


@app.route('/api/cache/clear', methods=['POST'])
async def cache_clear():
    """清空所有缓存"""
    temp_dir = Path("temp_segments")

    if not temp_dir.exists():
        return jsonify({
            "success": True,
            "deleted_count": 0,
            "message": "暂无缓存"
        })

    cache_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
    deleted_count = 0

    for cache_dir in cache_dirs:
        cache_manager_instance = CacheManager(
            temp_dir=str(temp_dir),
            url="",
            keep_cache=False
        )
        cache_manager_instance.cache_dir = cache_dir
        if cache_manager_instance.clear_cache():
            deleted_count += 1

    return jsonify({
        "success": True,
        "deleted_count": deleted_count,
        "message": f"已删除 {deleted_count}/{len(cache_dirs)} 个缓存"
    })


@app.route('/api/cache/update', methods=['POST'])
async def cache_update():
    """
    更新缓存元数据

    请求体:
    {
        "url": "https://example.com/video.m3u8"
    }
    """
    global logger

    try:
        data = await request.get_json()

        if not data or 'url' not in data:
            return jsonify({
                "success": False,
                "error": "缺少必要参数：url"
            }), 400

        url = data['url']

        config = AppConfig(
            url=url,
            threads=1,
            temp_dir="temp_segments",
            output_dir="output",
            max_download_rounds=1,
            keep_cache=True,
            ffmpeg_path=server_config.get("ffmpeg_path", "ffmpeg"),
        )

        cache_manager_instance = CacheManager(
            temp_dir=config.temp_dir,
            url=config.url,
            keep_cache=config.keep_cache
        )

        cache_manager_instance.init_cache()

        logger.info(f"正在更新缓存元数据：{url}")

        from parser import M3u8Parser
        parser = M3u8Parser(config, cache_manager_instance)
        parse_result = await parser.parse(force_refresh=True)

        if not parse_result.success:
            return jsonify({
                "success": False,
                "error": f"解析失败：{parse_result.error}"
            }), 500

        return jsonify({
            "success": True,
            "segment_count": len(parse_result.segments),
            "message": "缓存元数据更新完成"
        })

    except Exception as e:
        logger.error(f"更新缓存元数据时发生错误：{e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="m3u8 下载服务 API (异步版本)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --host 0.0.0.0 --port 8080
  %(prog)s --default-threads 16 --log-level DEBUG
  %(prog)s --log-dir /var/log/m3u8-downloader

API 端点:
  POST /api/download            - 提交异步下载任务
  GET  /api/tasks               - 列出所有任务
  GET  /api/tasks/<id>          - 查询任务状态
  DELETE /api/tasks/<id>        - 删除任务（运行中则先取消再删除，已结束则直接删除）
  POST /api/download/sync       - 同步下载（兼容旧 API）
        """
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="监听地址 IP (默认：127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="监听端口 (默认：5000)"
    )
    parser.add_argument(
        "--default-threads",
        type=int,
        default=8,
        metavar="N",
        help="默认下载并发数 (默认：8)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别 (默认：INFO)"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs",
        metavar="DIR",
        help="日志目录 (默认：logs)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式（等同于 --log-level DEBUG）"
    )
    return parser.parse_args()


def main():
    """主函数"""
    global logger, LOG_FILE, server_config

    args = parse_args()

    # 更新全局配置
    server_config["default_threads"] = args.default_threads

    # 设置日志级别
    log_level = logging.DEBUG if args.debug else getattr(logging, args.log_level.upper(), logging.INFO)

    # 更新日志目录
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 重新配置日志
    from logger import LOG_DIR, LOG_FILE as OLD_LOG_FILE
    import logger as logger_module
    logger_module.LOG_DIR = log_dir
    logger_module.LOG_FILE = log_dir / "m3u8-downloader.log"

    # 重新初始化 logger
    logger = setup_logger("api_server", level=log_level)
    setup_logger("parser", level=log_level)
    setup_logger("downloader", level=log_level)
    setup_logger("postprocessor", level=log_level)
    setup_logger("cache_manager", level=log_level)
    setup_logger("task_manager", level=log_level)

    logger.info(f"启动 m3u8 下载服务 API (异步版本)")
    logger.info(f"监听地址：{args.host}:{args.port}")
    logger.info(f"默认并发数：{server_config['default_threads']}")
    logger.info(f"日志级别：{logging.getLevelName(log_level)}")
    logger.info(f"日志目录：{log_dir}")

    # 启动 Quart 应用
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == "__main__":
    main()
