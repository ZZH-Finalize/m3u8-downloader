#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 视频下载工具 - 主程序
负责参数解析、模块协调和流程控制
"""

import sys
from pathlib import Path

from models import AppConfig
from parser import M3u8Parser
from downloader import SegmentDownloader
from postprocessor import MediaPostprocessor
from cache_manager import CacheManager
from logger import get_logger, LOG_FILE

logger = get_logger("main")


def create_parser() -> "argparse.ArgumentParser":
    """创建命令行参数解析器"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="m3u8 视频下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s https://example.com/video.m3u8
  %(prog)s https://example.com/video.m3u8 -j 8
  %(prog)s https://example.com/video.m3u8 --output-dir ./downloads -j 4
  %(prog)s https://example.com/video.m3u8 --keep-cache
        """,
    )

    parser.add_argument(
        "url",
        help="m3u8 文件的 URL",
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=4,
        metavar="N",
        help="下载线程数 (默认：4)",
    )
    parser.add_argument(
        "--temp-dir",
        type=str,
        default=None,
        metavar="PATH",
        help="分片临时存储目录 (默认：当前目录下的 temp_segments)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        metavar="PATH",
        help="输出文件目录 (默认：output)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=5,
        metavar="N",
        help="最大下载轮次 (默认：5)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式，输出详细日志",
    )
    parser.add_argument(
        "--keep-cache",
        action="store_true",
        help="保留缓存文件（m3u8 和分片），不自动清理",
    )

    return parser


def parse_arguments() -> AppConfig:
    """
    解析命令行参数并生成配置
    
    Returns:
        AppConfig: 应用配置
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # 验证参数
    if args.jobs < 1:
        logger.error("线程数必须大于 0")
        sys.exit(1)

    # 设置临时目录
    temp_dir = args.temp_dir or "temp_segments"

    # 启用调试模式
    if args.debug:
        get_logger("main", debug=True)
        get_logger("parser", debug=True)
        get_logger("downloader", debug=True)
        get_logger("postprocessor", debug=True)

    return AppConfig(
        url=args.url,
        threads=args.jobs,
        temp_dir=temp_dir,
        output_dir=args.output_dir,
        max_download_rounds=args.max_rounds,
        keep_cache=args.keep_cache,
    )


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


def run_parse(config: AppConfig, cache_manager: CacheManager) -> None:
    """
    执行解析阶段

    Args:
        config: 应用配置（会被修改）
        cache_manager: 缓存管理器
    """
    parser = M3u8Parser(config, cache_manager)
    result = parser.parse()

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


def main() -> None:
    """主函数"""
    # 1. 解析参数
    config = parse_arguments()

    # 2. 创建缓存管理器
    cache_manager = CacheManager(
        temp_dir=config.temp_dir,
        url=config.url,
        keep_cache=config.keep_cache
    )

    # 3. 设置输出文件路径 (output_dir/[hash]/video.mp4)
    output_dir = Path(config.output_dir) / cache_manager.cache_path.name
    output_dir.mkdir(parents=True, exist_ok=True)
    config.output_file = str(output_dir / "video.mp4")

    # 4. 打印启动信息
    logger.info("m3u8 下载工具启动")
    print_banner(config)

    # 5. 解析 m3u8
    run_parse(config, cache_manager)

    # 6. 下载分片
    run_download(config, cache_manager)

    # 7. 合并分片
    run_merge(config, cache_manager)

    logger.info("全部完成！日志文件：" + str(LOG_FILE))


if __name__ == "__main__":
    main()
