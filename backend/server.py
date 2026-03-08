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

# 全局配置（通过命令行参数设置）
server_config = {
    "default_threads": 8,
    "temp_dir": "data/temp_segments",
    "output_dir": "output",
}

logger = None  # 在 main() 中初始化

app = Quart(__name__)
app = cors(app)

# ===== 常量 =====
# 注意：实际目录由命令行参数或 server_config 配置，此处仅为默认值
DEFAULT_TEMP_DIR = "data/temp_segments"
DEFAULT_OUTPUT_DIR = "output"


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


def _validate_download_request(data: dict) -> tuple[bool, Optional[dict]]:
    """验证下载请求参数，返回 (是否有效，错误响应)"""
    if not data or 'url' not in data:
        return False, {"success": False, "error": "缺少必要参数：url"}
    if data.get('threads') is not None and data.get('threads') < 1:
        return False, {"success": False, "error": "线程数必须大于 0"}
    return True, None


def _create_task_from_request(data: dict) -> tuple:
    """从请求数据创建任务"""
    return task_manager.create_task(
        url=data['url'],
        threads=data.get('threads') if data.get('threads') is not None else server_config.get("default_threads", 8),
        output_dir=server_config.get("output_dir", DEFAULT_OUTPUT_DIR),
        temp_dir=server_config.get("temp_dir", DEFAULT_TEMP_DIR),
        max_rounds=data.get('max_rounds', 5),
        keep_cache=data.get('keep_cache', False),
        output_name=data.get('output'),
    )


def _handle_existing_task(task) -> Optional[dict]:
    """处理已存在的任务，返回响应或 None 表示可以继续"""
    status = task.progress.status

    if status == TaskStatus.FAILED:
        # 重启失败任务
        logger.info(f"发现失败任务 {task.task_id}，重新启动")
        task.progress.status = TaskStatus.PENDING
        task.progress.error = None
        task.progress.progress_percent = 0.0
        task.progress.current_step = "等待重启"
        task._cancel_flag = False
        task_manager.start_task(task.task_id)
        return {
            "success": True,
            "task_id": task.task_id,
            "status": "pending",
            "message": "失败任务已重启"
        }

    if status in [TaskStatus.PENDING, TaskStatus.PARSING, TaskStatus.DOWNLOADING, TaskStatus.MERGING]:
        logger.info(f"任务已存在且正在运行：{task.task_id}, 状态={status}")
        return {
            "success": False,
            "error": f"任务已存在且正在运行：{task.task_id}",
            "existing_task_id": task.task_id,
            "existing_status": status.value
        }

    logger.info(f"任务已存在：{task.task_id}, 状态={status}")
    return {
        "success": False,
        "error": f"任务已存在：{task.task_id}",
        "existing_task_id": task.task_id,
        "existing_status": status.value
    }


@app.route('/api/download', methods=['POST'])
async def download():
    """提交下载任务（异步）"""
    try:
        data = await request.get_json()

        valid, error_response = _validate_download_request(data)
        if not valid:
            return jsonify(error_response), 400

        if data.get('debug'):
            for module in ["api_server", "parser", "downloader", "postprocessor"]:
                get_logger(module, debug=True)

        logger.info(f"收到下载请求：URL={data['url']}")

        existing_task = task_manager.find_task_by_url(data['url'])
        if existing_task:
            response = _handle_existing_task(existing_task)
            if response:
                status_code = 409 if response.get('success') is False else 200
                return jsonify(response), status_code

        task = _create_task_from_request(data)
        task_manager.start_task(task.task_id)
        logger.info(f"任务已创建：{task.task_id}")

        return jsonify({
            "success": True,
            "task_id": task.task_id,
            "status": "pending",
            "message": "任务已提交，后台执行中"
        })

    except Exception as e:
        logger.error(f"处理下载请求时发生错误：{e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/download/sync', methods=['POST'])
async def download_sync():
    """同步下载（等待完成）- 用于兼容旧 API"""
    try:
        data = await request.get_json()

        valid, error_response = _validate_download_request(data)
        if not valid:
            return jsonify(error_response), 400

        logger.info(f"收到同步下载请求：URL={data['url']}")

        task = _create_task_from_request(data)
        result = await task_manager.execute_task(task)

        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 500 if not result.get("cancelled") else 400

    except Exception as e:
        logger.error(f"处理同步下载请求时发生错误：{e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/tasks', methods=['GET'])
async def list_tasks():
    """列出所有任务"""
    tasks = task_manager.list_tasks()
    return jsonify({"success": True, "tasks": tasks, "total_count": len(tasks)})


@app.route('/api/task/list', methods=['GET'])
async def list_task_ids():
    """列出所有任务 ID 及下载进度"""
    tasks = task_manager.list_tasks()

    task_list = [
        {
            "task_id": task["task_id"],
            "segments_downloaded": task["progress"].get("segments_downloaded", 0),
            "total_segments": task["progress"].get("total_segments", 0)
        }
        for task in tasks
    ]

    return jsonify({"success": True, "tasks": task_list, "total_count": len(task_list)})


@app.route('/api/tasks/<task_id>', methods=['GET'])
async def get_task_status(task_id: str):
    """获取任务状态"""
    result = task_manager.get_task_status(task_id)
    if result:
        return jsonify(result)
    return jsonify({"success": False, "error": "任务不存在"}), 404


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
async def delete_task(task_id: str):
    """删除任务"""
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    if task.progress.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        task_manager.cancel_task(task_id)

    task_manager.remove_task(task_id)
    return jsonify({"success": True, "message": f"任务已删除：{task_id}"})


# ===== 缓存管理 API =====

def _get_cache_manager(cache_dir: Path, keep_cache: bool = True) -> CacheManager:
    """创建 CacheManager 实例"""
    cm = CacheManager(temp_dir=str(cache_dir.parent), url="", keep_cache=keep_cache)
    cm.cache_dir = cache_dir
    return cm


def _build_cache_info(cache_dir: Path) -> dict:
    """构建缓存信息字典"""
    cm = _get_cache_manager(cache_dir)
    cache_info = cm.get_cache_info()
    metadata = cm.load_metadata()

    # 从元数据获取总分片数，如果元数据不存在则使用实际文件数
    segment_count = len(metadata.filenames) if metadata else cache_info["segment_count"]

    return {
        "id": cache_dir.name,
        "url": metadata.url if metadata else "未知",
        "segment_count": segment_count,
        "m3u8_count": cache_info["m3u8_count"],
        "total_size": cache_info["total_size"],
        "total_size_mb": round(cache_info["total_size"] / (1024 * 1024), 2),
        "created_at": metadata.created_at if metadata else None
    }


@app.route('/api/cache/list', methods=['GET'])
async def cache_list():
    """列出所有缓存"""
    temp_dir = Path(DEFAULT_TEMP_DIR)

    if not temp_dir.exists():
        return jsonify({"success": True, "caches": [], "total_count": 0})

    caches = [_build_cache_info(d) for d in temp_dir.iterdir() if d.is_dir()]

    return jsonify({"success": True, "caches": caches, "total_count": len(caches)})


@app.route('/api/cache/<cache_id>', methods=['GET'])
async def cache_get(cache_id: str):
    """获取指定缓存的详细信息"""
    cache_dir = Path(DEFAULT_TEMP_DIR) / cache_id

    if not cache_dir.exists():
        return jsonify({"success": False, "error": f"缓存不存在：{cache_id}"}), 404

    cm = _get_cache_manager(cache_dir)
    cache_info = cm.get_cache_info()
    metadata = cm.load_metadata()

    # 从元数据获取总分片数，如果元数据不存在则使用实际文件数
    segment_count = len(metadata.filenames) if metadata else cache_info["segment_count"]
    downloaded_count = metadata.get_downloaded_count() if metadata else 0

    return jsonify({
        "success": True,
        "cache": {
            "id": cache_id,
            "url": metadata.url if metadata else "未知",
            "base_url": metadata.base_url if metadata else None,
            "segment_count": segment_count,
            "m3u8_count": cache_info["m3u8_count"],
            "total_size": cache_info["total_size"],
            "total_size_mb": round(cache_info["total_size"] / (1024 * 1024), 2),
            "created_at": metadata.created_at if metadata else None,
            "downloaded_count": downloaded_count,
            "is_complete": metadata.is_complete if metadata else False
        }
    })

@app.route('/api/cache/<cache_id>', methods=['DELETE'])
async def cache_delete(cache_id: str):
    """删除指定缓存，但如果缓存被任务列表中的任务引用则拒绝删除"""
    cache_dir = Path(DEFAULT_TEMP_DIR) / cache_id

    if not cache_dir.exists():
        return jsonify({"success": False, "error": f"缓存不存在：{cache_id}"}), 404

    if cache_dir.name in _get_task_cache_ids():
        return jsonify({
            "success": False,
            "error": f"缓存 {cache_id} 正在被任务列表中的任务使用，无法删除",
            "code": "CACHE_IN_USE"
        }), 409

    cm = _get_cache_manager(cache_dir, keep_cache=False)
    success = cm.clear_cache()

    if success:
        return jsonify({"success": True, "message": f"缓存已删除：{cache_id}"})
    return jsonify({"success": False, "error": f"删除失败：{cache_id}"}), 500


def _get_task_cache_ids() -> set[str]:
    """获取任务列表中所有任务对应的缓存 ID"""
    return {
        CacheManager(
            temp_dir=task.config.temp_dir,
            url=task.config.url,
            keep_cache=task.config.keep_cache
        ).cache_dir.name
        for task in task_manager._tasks.values()
    }


@app.route('/api/cache/clear', methods=['POST'])
async def cache_clear():
    """清空所有缓存，但保留任务列表中任务对应的缓存"""
    temp_dir = Path(DEFAULT_TEMP_DIR)

    if not temp_dir.exists():
        return jsonify({"success": True, "deleted_count": 0, "message": "暂无缓存"})

    task_cache_ids = _get_task_cache_ids()
    deleted_count = 0
    skipped_count = 0

    for cache_dir in temp_dir.iterdir():
        if not cache_dir.is_dir():
            continue

        if cache_dir.name in task_cache_ids:
            logger.info(f"跳过缓存 {cache_dir.name}，因为任务列表中仍有任务引用它")
            skipped_count += 1
            continue

        if _get_cache_manager(cache_dir, keep_cache=False).clear_cache():
            deleted_count += 1

    return jsonify({
        "success": True,
        "deleted_count": deleted_count,
        "skipped_count": skipped_count,
        "message": f"已删除 {deleted_count} 个缓存，跳过 {skipped_count} 个（任务引用中）"
    })


@app.route('/api/cache/update', methods=['POST'])
async def cache_update():
    """更新缓存元数据"""
    try:
        data = await request.get_json()

        if not data or 'url' not in data:
            return jsonify({"success": False, "error": "缺少必要参数：url"}), 400

        url = data['url']
        logger.info(f"正在更新缓存元数据：{url}")

        config = AppConfig(
            url=url,
            threads=1,
            temp_dir=DEFAULT_TEMP_DIR,
            output_dir=DEFAULT_OUTPUT_DIR,
            max_download_rounds=1,
            keep_cache=True,
        )

        cm = CacheManager(temp_dir=config.temp_dir, url=config.url, keep_cache=config.keep_cache)
        cm.init_cache()

        from parser import M3u8Parser
        parser = M3u8Parser(config, cm)
        parse_result = await parser.parse(force_refresh=True)

        if not parse_result.success:
            return jsonify({"success": False, "error": f"解析失败：{parse_result.error}"}), 500

        return jsonify({
            "success": True,
            "segment_count": len(parse_result.segments),
            "message": "缓存元数据更新完成"
        })

    except Exception as e:
        logger.error(f"更新缓存元数据时发生错误：{e}")
        return jsonify({"success": False, "error": str(e)}), 500


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
        default=6900,
        help="监听端口 (默认：6900)"
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
    parser.add_argument(
        "--temp-dir",
        type=str,
        default="data/temp_segments",
        metavar="DIR",
        help="临时分片目录 (默认：data/temp_segments)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        metavar="DIR",
        help="输出目录 (默认：output)"
    )
    return parser.parse_args()


def main():
    """主函数"""
    global logger, LOG_FILE, server_config

    args = parse_args()

    # 更新全局配置
    server_config["default_threads"] = args.default_threads
    server_config["temp_dir"] = args.temp_dir
    server_config["output_dir"] = args.output_dir

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

    # 获取 hypercorn.access 日志记录器
    logging.getLogger('hypercorn.access').disabled = True

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
