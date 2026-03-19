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

import task
import argparse, asyncio
import logging, logger
from pathlib import Path
from models import DownloadArgs, DownloadResponse, TaskStatus, TaskInfo

from quart import Quart, request, jsonify
from quart_cors import cors

import config

logger_obj = logger.get_logger()

# ===== Quart 应用初始化 =====
app = cors(Quart(__name__))

# ===== API 端点 =====

@app.route('/health', methods=['GET'])
async def health_check():
    """健康检查端点"""
    return jsonify({'version': config.server.version})


@app.route('/api/config', methods=['GET'])
async def get_server_config():
    """获取服务器配置信息"""
    return jsonify(config.server.model_dump(mode='json'))


@app.route('/api/download', methods=['POST'])
async def download():
    """提交下载任务（异步）"""
    data = await request.get_json()

    param = DownloadArgs.model_validate(data)

    if not param.url:
        return jsonify(), 400

    # 限制 max_threads 不超过服务器配置
    param.threads = min(param.threads, config.server.max_threads)

    logger_obj.info(f'收到下载任务: {param.url}')

    response = await task.add(param)

    return jsonify(response.model_dump(mode='json'))


@app.route('/api/tasks', methods=['GET'])
async def list_tasks():
    """列出所有任务 ID 及下载进度"""
    return jsonify(task.list_task().model_dump(mode='json'))


@app.route('/api/tasks/<task_id>', methods=['GET'])
async def get_task_status(task_id: str):
    """获取任务状态"""
    response = task.get(task_id)

    if response is None:
        return jsonify(), 400

    return jsonify(response.model_dump(mode='json'))


@app.route('/api/tasks/<task_id>/pause', methods=['POST'])
async def pause_task(task_id: str):
    """暂停任务"""
    task.pause(task_id)

    return jsonify()


@app.route('/api/tasks/<task_id>/resume', methods=['POST'])
async def resume_task(task_id: str):
    """恢复任务"""
    task.resume(task_id)

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
        default=config.server.host,
        help=f"监听地址 IP (默认：{config.server.host})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.server.port,
        help=f"监听端口 (默认：{config.server.port})"
    )
    parser.add_argument(
        "--max-threads",
        type=int,
        default=config.server.max_threads,
        metavar="N",
        help=f"下载并发数上限 (默认：{config.server.max_threads})。如果 API 请求传入的 threads 值大于此值，将使用此值。"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=logging._levelToName[config.server.log_level],
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=f"日志级别 (默认：{logging._levelToName[config.server.log_level]})"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=config.server.log_dir,
        metavar="DIR",
        help=f"日志目录 (默认：{config.server.log_dir})"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式（等同于 --log-level DEBUG）"
    )
    parser.add_argument(
        "--temp-dir",
        type=str,
        default=config.server.temp_dir,
        metavar="DIR",
        help=f"临时分片目录 (默认：{config.server.temp_dir})"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=config.server.output_dir,
        metavar="DIR",
        help=f"输出目录 (默认：{config.server.output_dir})"
    )
    return parser.parse_args()


async def main():
    """主函数"""
    args = parse_args()

    # 将 argparse.Namespace 转换为字典
    args_dict = vars(args)

    # 设置日志级别 (字符串 -> int)
    log_level = logging.DEBUG if args.debug else getattr(logging, args.log_level.upper(), logging.INFO)
    args_dict['log_level'] = log_level

    # 使用 model_validate 创建 server_config
    config.update_server(args_dict)

    # 创建日志目录
    Path(config.server.log_dir).mkdir(parents=True, exist_ok=True)
    # 创建临时目录
    Path(config.server.temp_dir).mkdir(parents=True, exist_ok=True)
    # 创建输出目录
    Path(config.server.output_dir).mkdir(parents=True, exist_ok=True)

    logger.setup_logger(config.server)

    # 打印所有配置
    logging.info(f"启动 m3u8 下载服务")
    logging.info("===== 服务器配置 =====")
    logging.info(f"监听地址: {config.server.host}:{config.server.port}")
    logging.info(f"最大并发数: {config.server.max_threads}")
    logging.info(f"日志级别: {config.server.log_level}")
    logging.info(f"日志目录: {config.server.log_dir}")
    logging.info(f"调试模式: {config.server.debug}")
    logging.info(f"临时文件目录: {config.server.temp_dir}")
    logging.info(f"输出目录: {config.server.output_dir}")
    logging.info("======================")

    # 队列下载worker
    asyncio.create_task(task.queued_task_executor())

    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    # 使用 Hypercorn 启动 Quart 应用
    hypercorn_config = Config()
    hypercorn_config.bind = [f"{config.server.host}:{config.server.port}"]
    hypercorn_config.debug = config.server.debug

    await serve(app, hypercorn_config)

if __name__ == "__main__":
    asyncio.run(main())
