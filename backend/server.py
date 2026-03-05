#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 下载服务 - 后端 API 服务
提供 RESTful API 用于视频下载、缓存管理等功能
"""

import sys
import argparse
import logging
from pathlib import Path

# 添加当前目录到路径，确保模块导入正确
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import shutil

from models import AppConfig
from parser import M3u8Parser
from downloader import SegmentDownloader
from postprocessor import MediaPostprocessor
from cache_manager import CacheManager
from logger import get_logger, LOG_FILE, setup_logger

# 全局配置 - 会在 main() 中根据命令行参数设置
server_config = {
    "default_threads": 8,  # 默认下载线程数（当前端未提供时采用）
}

logger = None  # 在 main() 中初始化

app = Flask(__name__)
CORS(app)  # 启用 CORS 支持

# 存储正在进行的下载任务
active_tasks = {}


def create_app_config(
    url: str,
    threads: int = None,
    output_dir: str = "output",
    temp_dir: str = "temp_segments",
    max_rounds: int = 5,
    keep_cache: bool = False,
    output_name: str = None
) -> AppConfig:
    """创建应用配置"""
    # 如果前端未提供线程数，使用服务器默认值
    if threads is None:
        threads = server_config.get("default_threads", 8)
    
    config = AppConfig(
        url=url,
        threads=threads,
        temp_dir=temp_dir,
        output_dir=output_dir,
        max_download_rounds=max_rounds,
        keep_cache=keep_cache,
    )

    # 创建缓存管理器
    cache_manager = CacheManager(
        temp_dir=config.temp_dir,
        url=config.url,
        keep_cache=config.keep_cache
    )

    # 设置输出文件路径 (output_dir/[hash]/[output_name])
    output_name = output_name or "video.mp4"
    output_path = Path(config.output_dir) / cache_manager.cache_path.name / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config.output_file = str(output_path)

    return config


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "service": "m3u8-downloader-api"
    })


@app.route('/api/config', methods=['GET'])
def get_server_config():
    """获取服务器配置信息"""
    return jsonify({
        "default_threads": server_config.get("default_threads", 8),
        "log_level": logging.getLevelName(logger.level),
        "log_dir": str(LOG_FILE.parent)
    })


@app.route('/api/download', methods=['POST'])
def download():
    """
    下载 m3u8 视频

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
        "success": true/false,
        "output_path": "...",   // 输出文件路径（成功时）
        "segments_downloaded": 100,  // 成功下载的分片数
        "total_segments": 100        // 总分片数
        "error": "..."          // 错误信息（失败时）
    }
    """
    global logger
    
    try:
        data = request.get_json()

        if not data or 'url' not in data:
            return jsonify({
                "success": False,
                "error": "缺少必要参数：url"
            }), 400

        url = data['url']
        # 如果前端未提供线程数，使用服务器默认值
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

        # 创建配置（threads 为 None 时会使用服务器默认值）
        config = create_app_config(
            url=url,
            threads=threads,
            output_dir="output",
            temp_dir="temp_segments",
            max_rounds=max_rounds,
            keep_cache=keep_cache,
            output_name=output_name
        )

        # 创建缓存管理器
        cache_manager = CacheManager(
            temp_dir=config.temp_dir,
            url=config.url,
            keep_cache=config.keep_cache
        )

        logger.info(f"收到下载请求：URL={url}, 线程数={config.threads}")

        # 执行下载任务（同步）
        try:
            # 1. 解析 m3u8
            logger.info("开始解析 m3u8...")
            parser = M3u8Parser(config, cache_manager)
            parse_result = parser.parse()

            if not parse_result.success:
                return jsonify({
                    "success": False,
                    "error": f"解析失败：{parse_result.error}"
                }), 500

            config.parsed_segments = parse_result.segments
            logger.info(f"解析成功，共 {len(config.parsed_segments)} 个分片")

            # 2. 下载分片
            logger.info("开始下载分片...")
            downloader = SegmentDownloader(config, cache_manager)
            download_results = downloader.download_all(config.parsed_segments)

            # 统计结果
            success_count = sum(1 for r in download_results if r.success)
            failed_count = sum(1 for r in download_results if not r.success)

            if failed_count > 0:
                logger.warning(f"{failed_count} 个分片下载失败")

            if success_count == 0:
                return jsonify({
                    "success": False,
                    "error": "没有成功下载任何分片"
                }), 500

            logger.info(f"下载完成：{success_count}/{len(config.parsed_segments)} 个分片")

            # 保存下载路径
            config.downloaded_paths = downloader.get_success_paths(download_results)

            # 3. 合并分片
            logger.info("开始合并分片...")
            postprocessor = MediaPostprocessor(config)
            merge_result = postprocessor.merge(config.downloaded_paths)

            if not merge_result.success:
                return jsonify({
                    "success": False,
                    "error": f"合并失败：{merge_result.error}"
                }), 500

            # 合并成功后清理分片文件（保留元数据和 m3u8 文件）
            cache_manager.clear_segments()

            logger.info(f"下载完成，输出文件：{config.output_file}")

            return jsonify({
                "success": True,
                "output_path": config.output_file,
                "segments_downloaded": success_count,
                "total_segments": len(config.parsed_segments)
            })

        except Exception as e:
            logger.error(f"下载过程中发生错误：{e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    except Exception as e:
        logger.error(f"处理下载请求时发生错误：{e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in active_tasks:
        return jsonify({
            "success": False,
            "error": "任务不存在"
        }), 404

    task = active_tasks[task_id]
    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task.get("status", "unknown"),
        "progress": task.get("progress", 0),
        "result": task.get("result")
    })


# ===== 缓存管理 API =====

@app.route('/api/cache/list', methods=['GET'])
def cache_list():
    """
    列出所有缓存
    
    返回:
    {
        "success": true,
        "caches": [
            {
                "id": "abc123...",
                "url": "https://example.com/video.m3u8",
                "segment_count": 100,
                "m3u8_count": 2,
                "total_size": 10485760,
                "total_size_mb": 10.0,
                "created_at": "2024-01-01T12:00:00"
            }
        ],
        "total_count": 1
    }
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
def cache_get(cache_id):
    """
    获取指定缓存的详细信息
    
    返回:
    {
        "success": true,
        "cache": {
            "id": "abc123...",
            "url": "https://example.com/video.m3u8",
            "segment_count": 100,
            "m3u8_count": 2,
            "total_size": 10485760,
            "total_size_mb": 10.0,
            "created_at": "2024-01-01T12:00:00",
            "downloaded_count": 80,
            "is_complete": false
        }
    }
    """
    temp_dir = Path("temp_segments")
    cache_dir = temp_dir / cache_id
    
    if not cache_dir.exists():
        return jsonify({
            "success": False,
            "error": f"缓存不存在：{cache_id}"
        }), 404
    
    cache_manager = CacheManager(
        temp_dir=str(temp_dir),
        url="",
        keep_cache=True
    )
    cache_manager.cache_dir = cache_dir
    
    cache_info = cache_manager.get_cache_info()
    metadata = cache_manager.load_metadata()
    
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
def cache_delete(cache_id):
    """
    删除指定缓存
    
    返回:
    {
        "success": true/false,
        "error": "..."  // 失败时
    }
    """
    temp_dir = Path("temp_segments")
    cache_dir = temp_dir / cache_id
    
    if not cache_dir.exists():
        return jsonify({
            "success": False,
            "error": f"缓存不存在：{cache_id}"
        }), 404
    
    cache_manager = CacheManager(
        temp_dir=str(temp_dir),
        url="",
        keep_cache=False
    )
    cache_manager.cache_dir = cache_dir
    
    success = cache_manager.clear_cache()
    
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
def cache_clear():
    """
    清空所有缓存
    
    返回:
    {
        "success": true,
        "deleted_count": 5,
        "message": "已删除 5 个缓存"
    }
    """
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
        cache_manager = CacheManager(
            temp_dir=str(temp_dir),
            url="",
            keep_cache=False
        )
        cache_manager.cache_dir = cache_dir
        if cache_manager.clear_cache():
            deleted_count += 1
    
    return jsonify({
        "success": True,
        "deleted_count": deleted_count,
        "message": f"已删除 {deleted_count}/{len(cache_dirs)} 个缓存"
    })


@app.route('/api/cache/update', methods=['POST'])
def cache_update():
    """
    更新缓存元数据（重新下载 m3u8 并更新）
    
    请求体:
    {
        "url": "https://example.com/video.m3u8"
    }
    
    返回:
    {
        "success": true/false,
        "segment_count": 100,
        "message": "缓存元数据更新完成"
        "error": "..."  // 失败时
    }
    """
    global logger
    
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "success": False,
                "error": "缺少必要参数：url"
            }), 400
        
        url = data['url']
        
        # 创建配置
        config = AppConfig(
            url=url,
            threads=1,
            temp_dir="temp_segments",
            output_dir="output",
            max_download_rounds=1,
            keep_cache=True,
        )
        
        # 创建缓存管理器
        cache_manager = CacheManager(
            temp_dir=config.temp_dir,
            url=config.url,
            keep_cache=config.keep_cache
        )
        
        # 初始化缓存目录
        cache_manager.init_cache()
        
        logger.info(f"正在更新缓存元数据：{url}")
        
        # 执行解析（强制刷新）
        parser = M3u8Parser(config, cache_manager)
        parse_result = parser.parse(force_refresh=True)
        
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
        description="m3u8 下载服务 API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --host 0.0.0.0 --port 8080
  %(prog)s --default-threads 16 --log-level DEBUG
  %(prog)s --log-dir /var/log/m3u8-downloader
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
        help="默认下载线程数，当前端请求未提供时采用 (默认：8)"
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
        help="启用 Flask 调试模式（等同于 --log-level DEBUG）"
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
    # 修改模块级别的日志配置
    import logger as logger_module
    logger_module.LOG_DIR = log_dir
    logger_module.LOG_FILE = log_dir / "m3u8-downloader.log"
    
    # 重新初始化 logger
    logger = setup_logger("api_server", level=log_level)
    setup_logger("parser", level=log_level)
    setup_logger("downloader", level=log_level)
    setup_logger("postprocessor", level=log_level)
    setup_logger("cache_manager", level=log_level)
    
    logger.info(f"启动 m3u8 下载服务 API")
    logger.info(f"监听地址：{args.host}:{args.port}")
    logger.info(f"默认线程数：{server_config['default_threads']}")
    logger.info(f"日志级别：{logging.getLevelName(log_level)}")
    logger.info(f"日志目录：{log_dir}")

    # 启动 Flask 应用
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )


if __name__ == "__main__":
    main()
