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
  %(prog)s https://example.com/video.m3u8 -o ./downloads -j 4
  %(prog)s https://example.com/video.m3u8 -o output.mp4 -j 16
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
        "-o", "--output",
        type=str,
        default=None,
        metavar="PATH",
        help="输出文件路径或目录 (默认：当前目录下的 video.mp4)",
    )
    parser.add_argument(
        "--temp-dir",
        type=str,
        default=None,
        metavar="PATH",
        help="分片临时存储目录 (默认：当前目录下的 temp_segments)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式，输出详细日志",
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
    
    # 设置输出路径
    if args.output:
        output_path = Path(args.output)
        if output_path.suffix.lower() not in [".mp4", ".mkv", ".avi"]:
            # 作为目录处理
            output_path.mkdir(parents=True, exist_ok=True)
            output_file = str(output_path / "video.mp4")
        else:
            output_file = str(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_file = "video.mp4"
    
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
        output_file=output_file,
    )


def print_banner(config: AppConfig) -> None:
    """打印启动信息"""
    logger.info("=" * 40)
    logger.info(f"URL: {config.url}")
    logger.info(f"线程数：{config.threads}")
    logger.info(f"临时目录：{config.temp_dir}")
    logger.info(f"输出文件：{config.output_file}")
    logger.info("=" * 40)


def run_parse(config: AppConfig) -> None:
    """
    执行解析阶段
    
    Args:
        config: 应用配置（会被修改）
    """
    parser = M3u8Parser(config)
    result = parser.parse()
    
    if not result.success:
        logger.error(result.error)
        sys.exit(1)
    
    config.parsed_segments = result.segments


def run_download(config: AppConfig) -> None:
    """
    执行下载阶段
    
    Args:
        config: 应用配置（会被修改）
    """
    downloader = SegmentDownloader(config)
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


def run_merge(config: AppConfig) -> None:
    """
    执行合并阶段
    
    Args:
        config: 应用配置
    """
    postprocessor = MediaPostprocessor(config)
    result = postprocessor.merge(config.downloaded_paths)
    
    if not result.success:
        logger.warning(f"合并失败：{result.error}")
        logger.info("分片仍保留在临时目录中")
        sys.exit(1)


def main() -> None:
    """主函数"""
    # 1. 解析参数
    config = parse_arguments()
    
    # 2. 打印启动信息
    logger.info("m3u8 下载工具启动")
    print_banner(config)
    
    # 3. 解析 m3u8
    run_parse(config)
    
    # 4. 下载分片
    run_download(config)
    
    # 5. 合并分片
    run_merge(config)
    
    logger.info("全部完成！日志文件：" + str(LOG_FILE))


if __name__ == "__main__":
    main()
