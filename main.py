#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 视频下载工具 - 主程序
负责参数解析、模块协调和流程控制
"""

import sys
import argparse
from pathlib import Path

from models import AppConfig
from parser import M3u8Parser
from downloader import SegmentDownloader
from postprocessor import MediaPostprocessor
from cache_manager import CacheManager
from logger import get_logger, LOG_FILE

logger = get_logger("main")


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="m3u8 视频下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s download https://example.com/video.m3u8
  %(prog)s download https://example.com/video.m3u8 -j 8
  %(prog)s download https://example.com/video.m3u8 --output-dir ./downloads -j 4
  %(prog)s cache list
  %(prog)s cache rm https://example.com/video.m3u8
  %(prog)s cache clear
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

    # cache update
    cache_update_parser = cache_subparsers.add_parser("update", help="更新缓存元数据")
    cache_update_parser.add_argument(
        "url",
        help="要更新的 m3u8 URL",
    )

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


def setup_debug_logging() -> None:
    """启用调试模式"""
    get_logger("main", debug=True)
    get_logger("parser", debug=True)
    get_logger("downloader", debug=True)
    get_logger("postprocessor", debug=True)


def print_banner(config: AppConfig) -> None:
    """打印启动信息"""
    logger.info("=" * 40)
    logger.info(f"URL: {config.url}")
    logger.info(f"线程数：{config.threads}")
    logger.info(f"临时目录：{config.temp_dir}")
    logger.info(f"输出目录：{config.output_dir}")
    logger.info(f"输出文件：{config.output_file}")
    logger.info(f"最大下载轮次：{config.max_download_rounds}")
    logger.info(f"保留缓存：{config.keep_cache}")
    logger.info("=" * 40)


def run_parse(config: AppConfig, cache_manager: CacheManager, force_refresh: bool = False) -> None:
    """
    执行解析阶段

    Args:
        config: 应用配置（会被修改）
        cache_manager: 缓存管理器
        force_refresh: 是否强制刷新，忽略元数据缓存
    """
    parser = M3u8Parser(config, cache_manager)
    result = parser.parse(force_refresh=force_refresh)

    if not result.success:
        logger.error(result.error)
        sys.exit(1)

    config.parsed_segments = result.segments


def run_download(config: AppConfig, cache_manager: CacheManager) -> None:
    """
    执行下载阶段

    Args:
        config: 应用配置（会被修改）
        cache_manager: 缓存管理器
    """
    downloader = SegmentDownloader(config, cache_manager)
    results = downloader.download_all(config.parsed_segments)

    # 统计结果
    success_count = sum(1 for r in results if r.success)
    failed_count = sum(1 for r in results if not r.success)

    if failed_count > 0:
        logger.warning(f"{failed_count} 个分片下载失败")
        for r in results:
            if not r.success:
                logger.debug(f"失败分片：{r.segment.url} - {r.error}")

    if success_count == 0:
        logger.error("没有成功下载任何分片")
        sys.exit(1)

    logger.info(f"下载完成：{success_count}/{len(config.parsed_segments)} 个分片")

    # 保存下载路径
    config.downloaded_paths = downloader.get_success_paths(results)


def run_merge(config: AppConfig, cache_manager: CacheManager) -> None:
    """
    执行合并阶段

    Args:
        config: 应用配置
        cache_manager: 缓存管理器
    """
    postprocessor = MediaPostprocessor(config)
    result = postprocessor.merge(config.downloaded_paths)

    if not result.success:
        logger.warning(f"合并失败：{result.error}")
        logger.info("分片仍保留在临时目录中")
        sys.exit(1)

    # 合并成功后清理分片文件（保留元数据和 m3u8 文件）
    cache_manager.clear_segments()


def cmd_download(args: argparse.Namespace) -> None:
    """执行 download 命令"""
    # 验证参数
    if args.jobs < 1:
        logger.error("线程数必须大于 0")
        sys.exit(1)

    # 固定默认值
    temp_dir = "temp_segments"
    output_dir = "output"

    # 启用调试模式
    if args.debug:
        setup_debug_logging()

    # 创建配置
    config = AppConfig(
        url=args.url,
        threads=args.jobs,
        temp_dir=temp_dir,
        output_dir=output_dir,
        max_download_rounds=args.max_rounds,
        keep_cache=args.keep_cache,
    )

    # 创建缓存管理器
    cache_manager = CacheManager(
        temp_dir=config.temp_dir,
        url=config.url,
        keep_cache=config.keep_cache
    )

    # 设置输出文件路径 (output_dir/[hash]/[output_name])
    output_name = args.output or "video.mp4"
    output_path = Path(config.output_dir) / cache_manager.cache_path.name / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config.output_file = str(output_path)

    # 打印启动信息
    logger.info("m3u8 下载工具启动")
    print_banner(config)

    # 解析 m3u8
    run_parse(config, cache_manager)

    # 下载分片
    run_download(config, cache_manager)

    # 合并分片
    run_merge(config, cache_manager)

    logger.info("全部完成！日志文件：" + str(LOG_FILE))


def cmd_cache_list(args: argparse.Namespace) -> None:
    """执行 cache list 命令"""
    temp_dir = Path("temp_segments")

    if not temp_dir.exists():
        print("暂无缓存")
        return

    cache_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]

    if not cache_dirs:
        print("暂无缓存")
        return

    print(f"缓存目录：{temp_dir}")
    print("-" * 60)

    for cache_dir in cache_dirs:
        cache_manager = CacheManager(
            temp_dir=str(temp_dir),
            url="",  # 不需要 URL，只用于获取目录结构
            keep_cache=True
        )
        # 手动设置 cache_dir
        cache_manager.cache_dir = cache_dir

        cache_info = cache_manager.get_cache_info()
        size_mb = cache_info["total_size"] / (1024 * 1024)

        # 从元数据获取 URL
        metadata = cache_manager.load_metadata()
        url = metadata.url if metadata else "未知"

        print(f"\nURL: {url}")
        print(f"ID: {cache_dir.name}")
        print(f"  分片数量：{cache_info['segment_count']}")
        print(f"  m3u8 文件数：{cache_info['m3u8_count']}")
        print(f"  总大小：{size_mb:.2f} MB")

    print("-" * 60)
    print(f"共 {len(cache_dirs)} 个缓存")


def cmd_cache_rm(args: argparse.Namespace) -> None:
    """执行 cache rm 命令"""
    temp_dir = Path("temp_segments")

    if not temp_dir.exists():
        print(f"缓存不存在：{args.id}")
        return

    cache_dir = temp_dir / args.id

    if not cache_dir.exists():
        print(f"缓存不存在：{args.id}")
        return

    cache_manager = CacheManager(
        temp_dir=str(temp_dir),
        url="",
        keep_cache=False
    )
    cache_manager.cache_dir = cache_dir

    success = cache_manager.clear_cache()
    if success:
        print(f"缓存已删除：{args.id}")
    else:
        print(f"删除失败：{args.id}")


def cmd_cache_clear(args: argparse.Namespace) -> None:
    """执行 cache clear 命令"""
    temp_dir = Path("temp_segments")

    if not temp_dir.exists():
        print("暂无缓存")
        return

    cache_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]

    if not cache_dirs:
        print("暂无缓存")
        return

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

    print(f"已删除 {deleted_count}/{len(cache_dirs)} 个缓存")


def cmd_cache_update(args: argparse.Namespace) -> None:
    """执行 cache update 命令"""
    temp_dir = "temp_segments"

    # 创建缓存管理器
    cache_manager = CacheManager(
        temp_dir=temp_dir,
        url=args.url,
        keep_cache=True
    )

    # 初始化缓存目录
    cache_manager.init_cache()

    # 创建配置用于解析
    config = AppConfig(
        url=args.url,
        threads=1,
        temp_dir=temp_dir,
        output_dir="output",
        max_download_rounds=1,
        keep_cache=True,
    )

    logger.info(f"正在更新缓存元数据：{args.url}")

    # 检查是否有现有缓存
    if cache_manager.metadata_exists():
        logger.info("检测到现有缓存，将重新下载 m3u8 文件并更新元数据")
    else:
        logger.info("缓存不存在，将创建新缓存")

    # 执行解析（强制刷新，重新下载 m3u8 并生成/更新元数据）
    try:
        run_parse(config, cache_manager, force_refresh=True)
        logger.info("缓存元数据更新完成")
    except SystemExit:
        # run_parse 中调用了 sys.exit(1)，需要捕获
        logger.error("更新缓存元数据失败")
        sys.exit(1)


def cmd_cache(args: argparse.Namespace) -> None:
    """执行 cache 命令"""
    if not args.cache_action:
        # 没有指定子命令，显示帮助
        print("用法：m3u8-downloader cache <list|rm|clear|update>")
        print()
        print("子命令:")
        print("  list   列出所有缓存")
        print("  rm     删除指定 id 的缓存")
        print("  clear  清空所有缓存")
        print("  update 更新缓存元数据")
        print()
        print("使用 'm3u8-downloader cache <subcommand> --help' 获取更多信息")
        sys.exit(1)

    if args.cache_action == "list":
        cmd_cache_list(args)
    elif args.cache_action == "rm":
        cmd_cache_rm(args)
    elif args.cache_action == "clear":
        cmd_cache_clear(args)
    elif args.cache_action == "update":
        cmd_cache_update(args)
    else:
        print(f"未知的缓存操作：{args.cache_action}")
        sys.exit(1)


def main() -> None:
    """主函数"""
    command, args = parse_arguments()

    if command == "download":
        cmd_download(args)
    elif command == "cache":
        cmd_cache(args)
    else:
        print(f"未知命令：{command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
