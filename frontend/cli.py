#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 视频下载工具 - 前端 CLI
负责命令行参数解析和调用后端 API 服务
"""

import sys
import argparse
import requests
import time
from pathlib import Path


# 后端 API 服务地址
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 5000


def get_api_base_url(host: str, port: int) -> str:
    """获取 API 基础 URL"""
    return f"http://{host}:{port}"


def check_api_available(host: str, port: int) -> bool:
    """检查 API 服务是否可用"""
    try:
        response = requests.get(
            f"{get_api_base_url(host, port)}/health",
            timeout=5
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def add_api_args(parser: argparse.ArgumentParser) -> None:
    """为解析器添加 API 连接参数"""
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_API_HOST,
        help=f"后端 API 主机地址 (默认：{DEFAULT_API_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_API_PORT,
        help=f"后端 API 端口 (默认：{DEFAULT_API_PORT})",
    )


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="m3u8 视频下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s download https://example.com/video.m3u8
  %(prog)s download https://example.com/video.m3u8 -j 8
  %(prog)s download https://example.com/video.m3u8 --output video.mp4
  %(prog)s download https://example.com/video.m3u8 --host 192.168.1.100 --port 8080
  %(prog)s task list --host 192.168.1.100
  %(prog)s task status abc12345
  %(prog)s task delete abc12345
  %(prog)s cache list
  %(prog)s cache rm abc123
  %(prog)s cache clear
  %(prog)s config
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ===== download 子命令 =====
    download_parser = subparsers.add_parser(
        "download",
        help="下载 m3u8 视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
download 示例:
  %(prog)s https://example.com/video.m3u8
  %(prog)s https://example.com/video.m3u8 -j 8
  %(prog)s https://example.com/video.m3u8 --output video.mp4
  %(prog)s https://example.com/video.m3u8 --keep-cache
  %(prog)s https://example.com/video.m3u8 --host 192.168.1.100 --port 8080
        """,
    )

    download_parser.add_argument(
        "url",
        help="m3u8 文件的 URL",
    )
    download_parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=4,
        metavar="N",
        help="下载线程数 (默认：4)",
    )
    download_parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="NAME",
        help="输出文件名称 (默认：video.mp4)",
    )
    download_parser.add_argument(
        "--max-rounds",
        type=int,
        default=5,
        metavar="N",
        help="最大下载轮次 (默认：5)",
    )
    download_parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式，输出详细日志",
    )
    download_parser.add_argument(
        "--keep-cache",
        action="store_true",
        help="保留缓存文件（m3u8 和分片），不自动清理",
    )
    download_parser.add_argument(
        "--trace",
        action="store_true",
        help="启用进度跟踪，提交任务后轮询显示下载进度",
    )

    # API 连接参数
    add_api_args(download_parser)

    # ===== task 子命令 =====
    task_parser = subparsers.add_parser(
        "task",
        help="管理下载任务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
task 示例:
  %(prog)s list                        # 列出所有任务
  %(prog)s status <task_id>            # 查询任务状态
  %(prog)s delete <task_id>            # 删除任务（运行中则先取消再删除，已结束则直接删除）
  %(prog)s list --host 192.168.1.100   # 指定服务器地址
        """,
    )

    task_subparsers = task_parser.add_subparsers(dest="task_action", help="任务操作")

    # task list
    task_list_parser = task_subparsers.add_parser("list", help="列出所有任务")
    add_api_args(task_list_parser)

    # task status
    task_status_parser = task_subparsers.add_parser("status", help="查询任务状态")
    task_status_parser.add_argument(
        "task_id",
        help="任务 ID",
    )
    add_api_args(task_status_parser)

    # task delete
    task_delete_parser = task_subparsers.add_parser("delete", help="删除任务")
    task_delete_parser.add_argument(
        "task_id",
        help="要删除的任务 ID",
    )
    add_api_args(task_delete_parser)

    # ===== cache 子命令 =====
    cache_parser = subparsers.add_parser(
        "cache",
        help="管理缓存",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
cache 示例:
  %(prog)s list                          # 列出所有缓存
  %(prog)s rm <id>                       # 删除指定 id 的缓存
  %(prog)s clear                         # 清空所有缓存
  %(prog)s update <url>                  # 更新指定 URL 的缓存元数据
  %(prog)s info <id>                     # 获取缓存详情
  %(prog)s list --host 192.168.1.100     # 指定服务器地址
        """,
    )

    cache_subparsers = cache_parser.add_subparsers(dest="cache_action", help="缓存操作")

    # cache list
    cache_list_parser = cache_subparsers.add_parser("list", help="列出所有缓存")
    add_api_args(cache_list_parser)

    # cache rm
    cache_rm_parser = cache_subparsers.add_parser("rm", help="删除指定 id 的缓存")
    cache_rm_parser.add_argument(
        "id",
        help="要删除缓存的 id (哈希值)",
    )
    add_api_args(cache_rm_parser)

    # cache clear
    cache_clear_parser = cache_subparsers.add_parser("clear", help="清空所有缓存")
    add_api_args(cache_clear_parser)

    # cache update
    cache_update_parser = cache_subparsers.add_parser("update", help="更新缓存元数据")
    cache_update_parser.add_argument(
        "url",
        help="要更新的 m3u8 URL",
    )
    add_api_args(cache_update_parser)

    # cache info
    cache_info_parser = cache_subparsers.add_parser("info", help="获取缓存详情")
    cache_info_parser.add_argument(
        "id",
        help="缓存 ID",
    )
    add_api_args(cache_info_parser)

    # ===== config 子命令 =====
    config_parser = subparsers.add_parser(
        "config",
        help="获取服务器配置",
    )
    add_api_args(config_parser)

    return parser


def parse_arguments() -> tuple[str, argparse.Namespace]:
    """
    解析命令行参数

    Returns:
        (command, args): 命令名称和参数对象
    """
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    return args.command, args


def cmd_download(args: argparse.Namespace) -> None:
    """执行 download 命令"""
    # 验证参数
    if args.jobs < 1:
        print(f"错误：线程数必须大于 0", file=sys.stderr)
        sys.exit(1)

    # 检查 API 服务是否可用
    if not check_api_available(args.host, args.port):
        print(f"错误：无法连接到后端 API 服务 ({args.host}:{args.port})", file=sys.stderr)
        print(f"请确保后端服务正在运行", file=sys.stderr)
        sys.exit(1)

    api_base_url = get_api_base_url(args.host, args.port)

    print(f"正在连接到后端服务：{api_base_url}")
    print(f"URL: {args.url}")
    print(f"线程数：{args.jobs}")
    print(f"输出文件：{args.output or 'video.mp4'}")
    if args.trace:
        print(f"模式：进度跟踪")
    print("-" * 40)

    # 构建请求体
    payload = {
        "url": args.url,
        "threads": args.jobs,
        "output": args.output,
        "max_rounds": args.max_rounds,
        "keep_cache": args.keep_cache,
        "debug": args.debug,
    }

    try:
        # 发送下载请求
        response = requests.post(
            f"{api_base_url}/api/download",
            json=payload,
            timeout=60 * 60  # 1 小时超时
        )

        result = response.json()

        if not result.get("success"):
            print(f"下载失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

        task_id = result.get('task_id')
        print(f"任务已提交!")
        print(f"任务 ID: {task_id}")

        # 如果启用 trace 模式，轮询跟踪进度
        if args.trace:
            _trace_task_progress(api_base_url, task_id)
        else:
            print(f"状态：{result.get('status')}")
            print(f"提示：使用 'm3u8-downloader task status {task_id}' 查询进度")

    except requests.exceptions.Timeout:
        print(f"错误：请求超时", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def _trace_task_progress(api_base_url: str, task_id: str) -> None:
    """
    轮询跟踪任务进度

    Args:
        api_base_url: API 基础 URL
        task_id: 任务 ID
    """
    last_status = None
    last_percent = None

    try:
        while True:
            response = requests.get(
                f"{api_base_url}/api/tasks/{task_id}",
                timeout=30
            )
            result = response.json()

            if not result.get("success"):
                print(f"\n错误：获取任务状态失败：{result.get('error')}", file=sys.stderr)
                break

            progress = result.get("progress", {})
            status = progress.get("status", "未知")
            percent = progress.get("progress_percent", 0)
            current_step = progress.get("current_step", "")
            downloaded = progress.get("segments_downloaded", 0)
            total = progress.get("total_segments", 0)
            error = progress.get("error")

            # 构建状态显示
            status_display = f"[{status.upper()}]"
            if status != last_status or percent != last_percent:
                # 状态或进度变化时显示新行
                if last_status is not None:
                    print()  # 换行
                print(f"{status_display} {current_step} {percent:.1f}% ({downloaded}/{total})")
                last_status = status
                last_percent = percent
            else:
                # 状态未变化时，在同一行更新（可选）
                pass

            # 检查是否结束
            if status in ("completed", "failed", "cancelled"):
                print("-" * 40)
                if status == "completed":
                    print(f"下载完成!")
                    download_result = progress.get("result", {})
                    if download_result:
                        print(f"输出文件：{download_result.get('output_path', '未知')}")
                        print(f"分片：{download_result.get('segments_downloaded', 0)}/{download_result.get('total_segments', 0)}")
                elif status == "failed":
                    print(f"下载失败：{error}", file=sys.stderr)
                elif status == "cancelled":
                    print(f"任务已取消")
                break

            # 轮询间隔 0.5 秒
            time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n\n跟踪已中断")
        print(f"提示：使用 'm3u8-downloader task status {task_id}' 继续查询进度")
        sys.exit(0)
    except requests.exceptions.RequestException as e:
        print(f"\n错误：轮询失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_task_list(args: argparse.Namespace) -> None:
    """执行 task list 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.get(f"{api_base_url}/api/tasks", timeout=30)
        result = response.json()

        if not result.get("success"):
            print(f"获取任务列表失败：{result.get('error')}", file=sys.stderr)
            return

        tasks = result.get("tasks", [])

        if not tasks:
            print("暂无任务")
            return

        print(f"任务列表:")
        print("-" * 80)

        for task in tasks:
            task_id = task.get("task_id", "未知")
            url = task.get("url", "未知")
            progress = task.get("progress", {})
            status = progress.get("status", "未知")
            percent = progress.get("progress_percent", 0)
            downloaded = progress.get("segments_downloaded", 0)
            total = progress.get("total_segments", 0)

            print(f"\n任务 ID: {task_id}")
            print(f"  URL: {url}")
            print(f"  状态：{status}")
            print(f"  进度：{percent:.1f}% ({downloaded}/{total})")

        print("-" * 80)
        print(f"共 {len(tasks)} 个任务")

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_task_status(args: argparse.Namespace) -> None:
    """执行 task status 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.get(f"{api_base_url}/api/tasks/{args.task_id}", timeout=30)
        result = response.json()

        if response.status_code == 404:
            print(f"错误：任务不存在：{args.task_id}", file=sys.stderr)
            sys.exit(1)

        if not result.get("success"):
            print(f"获取任务状态失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

        task_id = result.get("task_id", args.task_id)
        url = result.get("url", "未知")
        progress = result.get("progress", {})

        status = progress.get("status", "未知")
        percent = progress.get("progress_percent", 0)
        current_step = progress.get("current_step", "")
        downloaded = progress.get("segments_downloaded", 0)
        total = progress.get("total_segments", 0)
        error = progress.get("error")
        created_at = progress.get("created_at", "")
        started_at = progress.get("started_at", "")
        completed_at = progress.get("completed_at", "")

        print(f"任务状态:")
        print("-" * 50)
        print(f"任务 ID: {task_id}")
        print(f"URL: {url}")
        print(f"状态：{status}")
        print(f"进度：{percent:.1f}% ({downloaded}/{total})")
        if current_step:
            print(f"当前步骤：{current_step}")
        if error:
            print(f"错误：{error}", file=sys.stderr)
        if created_at:
            print(f"创建时间：{created_at}")
        if started_at:
            print(f"开始时间：{started_at}")
        if completed_at:
            print(f"完成时间：{completed_at}")
        print("-" * 50)

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_task_delete(args: argparse.Namespace) -> None:
    """执行 task delete 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.delete(
            f"{api_base_url}/api/tasks/{args.task_id}",
            timeout=30
        )
        result = response.json()

        if result.get("success"):
            print(f"任务已删除：{args.task_id}")
        else:
            print(f"删除失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_task(args: argparse.Namespace) -> None:
    """执行 task 命令"""
    if not args.task_action:
        # 没有指定子命令，显示帮助
        print("用法：m3u8-downloader task <list|status|delete>")
        print()
        print("子命令:")
        print("  list    列出所有任务")
        print("  status  查询任务状态")
        print("  delete  删除任务（运行中则先取消再删除，已结束则直接删除）")
        print()
        print("使用 'm3u8-downloader task <subcommand> --help' 获取更多信息")
        sys.exit(1)

    # 检查 API 服务是否可用
    if not check_api_available(args.host, args.port):
        print(f"错误：无法连接到后端 API 服务 ({args.host}:{args.port})", file=sys.stderr)
        print(f"请确保后端服务正在运行", file=sys.stderr)
        sys.exit(1)

    if args.task_action == "list":
        cmd_task_list(args)
    elif args.task_action == "status":
        cmd_task_status(args)
    elif args.task_action == "delete":
        cmd_task_delete(args)
    else:
        print(f"未知的任务操作：{args.task_action}", file=sys.stderr)
        sys.exit(1)


def cmd_cache_list(args: argparse.Namespace) -> None:
    """执行 cache list 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.get(f"{api_base_url}/api/cache/list", timeout=30)
        result = response.json()

        if not result.get("success"):
            print(f"获取缓存列表失败：{result.get('error')}", file=sys.stderr)
            return

        caches = result.get("caches", [])

        if not caches:
            print("暂无缓存")
            return

        print(f"缓存目录：temp_segments")
        print("-" * 70)

        for cache in caches:
            print(f"\nURL: {cache['url']}")
            print(f"ID: {cache['id']}")
            print(f"  分片数量：{cache['segment_count']}")
            print(f"  m3u8 文件数：{cache['m3u8_count']}")
            print(f"  总大小：{cache['total_size_mb']:.2f} MB")
            if cache.get('created_at'):
                print(f"  创建时间：{cache['created_at']}")

        print("-" * 70)
        print(f"共 {len(caches)} 个缓存")

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cache_info(args: argparse.Namespace) -> None:
    """执行 cache info 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.get(f"{api_base_url}/api/cache/{args.id}", timeout=30)
        result = response.json()

        if response.status_code == 404:
            print(f"错误：缓存不存在：{args.id}", file=sys.stderr)
            sys.exit(1)

        if not result.get("success"):
            print(f"获取缓存详情失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

        cache = result.get("cache", {})

        print(f"缓存详情:")
        print("-" * 50)
        print(f"ID: {cache.get('id', args.id)}")
        print(f"URL: {cache.get('url', '未知')}")
        if cache.get('base_url'):
            print(f"基准 URL: {cache.get('base_url')}")
        print(f"分片数量：{cache.get('segment_count', 0)}")
        print(f"m3u8 文件数：{cache.get('m3u8_count', 0)}")
        print(f"总大小：{cache.get('total_size_mb', 0):.2f} MB")
        print(f"已下载：{cache.get('downloaded_count', 0)}/{cache.get('segment_count', 0)}")
        print(f"完成状态：{'是' if cache.get('is_complete') else '否'}")
        if cache.get('created_at'):
            print(f"创建时间：{cache.get('created_at')}")
        print("-" * 50)

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cache_rm(args: argparse.Namespace) -> None:
    """执行 cache rm 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.delete(
            f"{api_base_url}/api/cache/{args.id}",
            timeout=30
        )
        result = response.json()

        if result.get("success"):
            print(f"缓存已删除：{args.id}")
        else:
            print(f"删除失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cache_clear(args: argparse.Namespace) -> None:
    """执行 cache clear 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.post(
            f"{api_base_url}/api/cache/clear",
            timeout=30
        )
        result = response.json()

        if result.get("success"):
            print(f"{result.get('message')}")
        else:
            print(f"清空失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cache_update(args: argparse.Namespace) -> None:
    """执行 cache update 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    print(f"正在更新缓存元数据：{args.url}")

    try:
        response = requests.post(
            f"{api_base_url}/api/cache/update",
            json={"url": args.url},
            timeout=300  # 5 分钟超时
        )
        result = response.json()

        if result.get("success"):
            print(f"缓存元数据更新完成，共 {result.get('segment_count')} 个分片")
        else:
            print(f"更新失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

    except requests.exceptions.Timeout:
        print(f"错误：请求超时", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cache(args: argparse.Namespace) -> None:
    """执行 cache 命令"""
    if not args.cache_action:
        # 没有指定子命令，显示帮助
        print("用法：m3u8-downloader cache <list|info|rm|clear|update>")
        print()
        print("子命令:")
        print("  list   列出所有缓存")
        print("  info   获取缓存详情")
        print("  rm     删除指定 id 的缓存")
        print("  clear  清空所有缓存")
        print("  update 更新缓存元数据")
        print()
        print("使用 'm3u8-downloader cache <subcommand> --help' 获取更多信息")
        sys.exit(1)

    # 检查 API 服务是否可用
    if not check_api_available(args.host, args.port):
        print(f"错误：无法连接到后端 API 服务 ({args.host}:{args.port})", file=sys.stderr)
        print(f"请确保后端服务正在运行", file=sys.stderr)
        sys.exit(1)

    if args.cache_action == "list":
        cmd_cache_list(args)
    elif args.cache_action == "info":
        cmd_cache_info(args)
    elif args.cache_action == "rm":
        cmd_cache_rm(args)
    elif args.cache_action == "clear":
        cmd_cache_clear(args)
    elif args.cache_action == "update":
        cmd_cache_update(args)
    else:
        print(f"未知的缓存操作：{args.cache_action}", file=sys.stderr)
        sys.exit(1)


def cmd_config(args: argparse.Namespace) -> None:
    """执行 config 命令"""
    api_base_url = get_api_base_url(args.host, args.port)

    try:
        response = requests.get(f"{api_base_url}/api/config", timeout=30)
        result = response.json()

        if not result.get("success") and "success" in result:
            print(f"获取配置失败：{result.get('error')}", file=sys.stderr)
            sys.exit(1)

        print(f"服务器配置:")
        print("-" * 30)
        print(f"默认线程数：{result.get('default_threads', '未知')}")
        print(f"日志级别：{result.get('log_level', '未知')}")
        print(f"日志目录：{result.get('log_dir', '未知')}")
        print("-" * 30)

    except requests.exceptions.RequestException as e:
        print(f"错误：请求失败 - {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """主函数"""
    command, args = parse_arguments()

    if command == "download":
        cmd_download(args)
    elif command == "task":
        cmd_task(args)
    elif command == "cache":
        cmd_cache(args)
    elif command == "config":
        cmd_config(args)
    else:
        print(f"未知命令：{command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
