#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 下载服务 - 后端 API 服务
提供 RESTful API 用于视频下载、缓存管理等功能
"""

import sys
import argparse
from pathlib import Path

# 添加当前目录到路径，确保模块导入正确
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify
from flask_cors import CORS
import threading

from models import AppConfig
from parser import M3u8Parser
from downloader import SegmentDownloader
from postprocessor import MediaPostprocessor
from cache_manager import CacheManager
from logger import get_logger, LOG_FILE

logger = get_logger("api_server")

app = Flask(__name__)
CORS(app)  # 启用 CORS 支持

# 存储正在进行的下载任务
active_tasks = {}


def create_app_config(
    url: str,
    threads: int = 4,
    output_dir: str = "output",
    temp_dir: str = "temp_segments",
    max_rounds: int = 5,
    keep_cache: bool = False,
    output_name: str = None
) -> AppConfig:
    """创建应用配置"""
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


@app.route('/api/download', methods=['POST'])
def download():
    """
    下载 m3u8 视频
    
    请求体:
    {
        "url": "https://example.com/video.m3u8",
        "threads": 4,          // 可选，默认 4
        "output": "video.mp4",  // 可选，默认 video.mp4
        "max_rounds": 5,        // 可选，默认 5
        "keep_cache": false,    // 可选，默认 false
        "debug": false          // 可选，默认 false
    }
    
    返回:
    {
        "success": true/false,
        "task_id": "xxx",       // 任务 ID
        "output_path": "...",   // 输出文件路径（成功时）
        "error": "..."          // 错误信息（失败时）
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "success": False,
                "error": "缺少必要参数：url"
            }), 400
        
        url = data['url']
        threads = data.get('threads', 4)
        output_name = data.get('output')
        max_rounds = data.get('max_rounds', 5)
        keep_cache = data.get('keep_cache', False)
        debug = data.get('debug', False)
        
        # 验证参数
        if threads < 1:
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
        
        # 创建配置
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
        
        logger.info(f"收到下载请求：URL={url}, 线程数={threads}")
        
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


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="m3u8 下载服务 API")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="监听地址 (默认：127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="监听端口 (默认：5000)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用 Flask 调试模式"
    )
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    logger.info(f"启动 m3u8 下载服务 API，监听 {args.host}:{args.port}")
    
    # 启动 Flask 应用
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )


if __name__ == "__main__":
    main()
