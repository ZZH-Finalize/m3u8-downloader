#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 视频下载工具 - 前端 CLI
负责命令行参数解析和调用后端 API 服务
"""

import sys
import argparse
import requests
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
  %(prog)s download https://example.com/video.m3u8 --api-host 192.168.1.100 --api-port 5000
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
    
    # API 连接参数
    download_parser.add_argument(
        "--api-host",
        type=str,
        default=DEFAULT_API_HOST,
        help=f"后端 API 主机地址 (默认：{DEFAULT_API_HOST})",
    )
    download_parser.add_argument(
        "--api-port",
        type=int,
        default=DEFAULT_API_PORT,
        help=f"后端 API 端口 (默认：{DEFAULT_API_PORT})",
    )

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
        """,
    )

    cache_subparsers = cache_parser.add_subparsers(dest="cache_action", help="缓存操作")

    # cache list
    cache_list_parser = cache_subparsers.add_parser("list", help="列出所有缓存")

    # cache rm
    cache_rm_parser = cache_subparsers.add_parser("rm", help="删除指定 id 的缓存")
    cache_rm_parser.add_argument(
        "id",
        help="要删除缓存的 id (哈希值)",
    )

    # cache clear
    cache_clear_parser = cache_subparsers.add_parser("clear", help="清空所有缓存")

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
    if not check_api_available(args.api_host, args.api_port):
        print(f"错误：无法连接到后端 API 服务 ({args.api_host}:{args.api_port})", file=sys.stderr)
        print(f"请确保后端服务正在运行", file=sys.stderr)
        sys.exit(1)
    
    api_base_url = get_api_base_url(args.api_host, args.api_port)
    
    print(f"正在连接到后端服务：{api_base_url}")
    print(f"URL: {args.url}")
    print(f"线程数：{args.jobs}")
    print(f"输出文件：{args.output or 'video.mp4'}")
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
        
        if result.get("success"):
            print("-" * 40)
            print(f"下载完成!")
            print(f"输出文件：{result.get('output_path')}")
            print(f"分片：{result.get('segments_downloaded')}/{result.get('total_segments')}")
        else:
            print(f"下载失败：{result.get('error')}", file=sys.stderr)
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
        print("用法：m3u8-downloader cache <list|rm|clear>")
        print()
        print("子命令:")
        print("  list   列出所有缓存")
        print("  rm     删除指定 id 的缓存")
        print("  clear  清空所有缓存")
        print()
        print("使用 'm3u8-downloader cache <subcommand> --help' 获取更多信息")
        sys.exit(1)
    
    # 检查 API 服务是否可用
    api_host = DEFAULT_API_HOST
    api_port = DEFAULT_API_PORT
    
    if not check_api_available(api_host, api_port):
        print(f"错误：无法连接到后端 API 服务 ({api_host}:{api_port})", file=sys.stderr)
        print(f"请确保后端服务正在运行", file=sys.stderr)
        sys.exit(1)
    
    if args.cache_action == "list":
        print("缓存管理功能待实现")
    elif args.cache_action == "rm":
        print(f"删除缓存功能待实现：{args.id}")
    elif args.cache_action == "clear":
        print("清空缓存功能待实现")
    else:
        print(f"未知的缓存操作：{args.cache_action}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """主函数"""
    command, args = parse_arguments()

    if command == "download":
        cmd_download(args)
    elif command == "cache":
        cmd_cache(args)
    else:
        print(f"未知命令：{command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
