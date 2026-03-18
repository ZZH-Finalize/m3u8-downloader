#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 下载服务 - 异步后端 API 服务 (重写版)

架构说明:
- 使用 Quart 异步框架 (Flask 的异步版本)
- 前台任务：响应 API 请求（立即返回）
- 后台任务：下载分片、转码等（异步执行）
- 任务管理器：跟踪和管理所有后台任务
"""

import sys
import argparse
import logging, logger
from pathlib import Path
from models import DownloadArgs, DownloadResponse

from quart import Quart, request, jsonify
from quart_cors import cors

from config import ServerConfig, server_config

# ===== Quart 应用初始化 =====
app = cors(Quart(__name__))

# ===== API 端点 =====

@app.route('/health', methods=['GET'])
async def health_check():
    """健康检查端点"""
    return jsonify()


@app.route('/api/config', methods=['GET'])
async def get_server_config():
    """获取服务器配置信息"""
    return jsonify(server_config)


@app.route('/api/download', methods=['POST'])
async def download():
    """提交下载任务（异步）"""
    return jsonify()


@app.route('/api/tasks', methods=['GET'])
async def list_tasks():
    """列出所有任务 ID 及下载进度"""
    return jsonify()


@app.route('/api/tasks/<task_id>', methods=['GET'])
async def get_task_status(task_id: str):
    """获取任务状态"""
    return jsonify()


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
async def delete_task(task_id: str):
    """删除任务"""
    return jsonify()


# ===== 缓存管理 API =====

@app.route('/api/cache/list', methods=['GET'])
async def cache_list():
    """列出所有缓存"""
    return jsonify()


@app.route('/api/cache/<cache_id>', methods=['GET'])
async def cache_get(cache_id: str):
    """获取指定缓存的详细信息"""
    return jsonify()


@app.route('/api/cache/<cache_id>', methods=['DELETE'])
async def cache_delete(cache_id: str):
    """删除指定缓存，但如果缓存被任务列表中的任务引用则拒绝删除"""
    return jsonify()


@app.route('/api/cache/clear', methods=['POST'])
async def cache_clear():
    """清空所有缓存，但保留任务列表中任务对应的缓存"""
    return jsonify()


@app.route('/api/cache/update', methods=['POST'])
async def cache_update():
    """更新缓存元数据"""
    return jsonify()


# ===== 命令行参数解析 =====

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="m3u8 下载服务 API (异步版本)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --host 0.0.0.0 --port 8080
  %(prog)s --max-threads 16 --log-level DEBUG
  %(prog)s --log-dir /var/log/m3u8-downloader

API 端点:
  POST /api/download            - 提交异步下载任务
  GET  /api/tasks               - 列出所有任务
  GET  /api/tasks/<id>          - 查询任务状态
  DELETE /api/tasks/<id>        - 删除任务（运行中则先取消再删除，已结束则直接删除）
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
        "--max-threads",
        type=int,
        default=32,
        metavar="N",
        help="下载并发数上限 (默认：32)。如果 API 请求传入的 threads 值大于此值，将使用此值。"
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
    global server_config

    args = parse_args()

    # 将 argparse.Namespace 转换为字典
    args_dict = vars(args)

    # 设置日志级别 (字符串 -> int)
    log_level = logging.DEBUG if args.debug else getattr(logging, args.log_level.upper(), logging.INFO)
    args_dict['log_level'] = log_level

    # 使用 model_validate 创建 server_config
    server_config = ServerConfig.model_validate(args_dict)

    # 创建日志目录
    Path(server_config.log_dir).mkdir(parents=True, exist_ok=True)
    # 创建临时目录
    Path(server_config.temp_dir).mkdir(parents=True, exist_ok=True)
    # 创建输出目录
    Path(server_config.output_dir).mkdir(parents=True, exist_ok=True)

    # TODO: 初始化日志系统
    logger.setup_logger(server_config)

    # 打印所有配置
    logging.info(f"启动 m3u8 下载服务")
    logging.info("===== 服务器配置 =====")
    logging.info(f"监听地址: {server_config.host}:{server_config.port}")
    logging.info(f"最大并发数: {server_config.max_threads}")
    logging.info(f"日志级别: {server_config.log_level}")
    logging.info(f"日志目录: {server_config.log_dir}")
    logging.info(f"调试模式: {server_config.debug}")
    logging.info(f"临时文件目录: {server_config.temp_dir}")
    logging.info(f"输出目录: {server_config.output_dir}")
    logging.info("======================")

    # 启动 Quart 应用
    # app.run(
    #     host=args.host,
    #     port=args.port,
    #     debug=args.debug
    # )
    import asyncio
    from steps import download

    # asyncio.run(download('https://asmr.121231234.xyz/asmr6/%E5%B0%8F%E7%8B%B8/31.m3u8?sign=Xaw-ie3jzZxpyBO9cUzBN0j57OUaGSZwjPMoIhIxoAA=:1851477223'))
    asyncio.run(download('https://surrit.com/2439bebd-d0fb-479e-83f8-acd86b8f9c2c/playlist.m3u8'))


if __name__ == "__main__":
    main()
