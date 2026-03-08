#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存管理模块
负责 m3u8 文件和分片文件的缓存管理
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from logger import get_logger
from models import MetaData

logger = get_logger("cache_manager")


class CacheManager:
    """
    缓存管理器

    负责：
    1. 管理 m3u8 文件缓存（主列表和分辨率子列表）
    2. 管理分片文件缓存
    3. 缓存清理
    """

    # m3u8 缓存文件命名
    MASTER_M3U8_FILENAME = "master.m3u8"  # 主 m3u8 列表
    RESOLUTION_M3U8_PATTERN = "{}p.m3u8"  # 分辨率 m3u8 文件命名模板
    METADATA_FILENAME = "metadata.json"  # 元数据文件名

    def __init__(self, temp_dir: str, url: str, keep_cache: bool = False):
        """
        初始化缓存管理器

        Args:
            temp_dir: 临时目录根路径
            url: 原始 URL，用于生成缓存子目录
            keep_cache: 是否保留缓存
        """
        self.temp_dir = Path(temp_dir)
        self.url = url
        self.keep_cache = keep_cache
        self.cache_dir = self._get_cache_dir()

    def _get_cache_dir(self) -> Path:
        """根据 URL 生成缓存子目录"""
        url_hash = hashlib.md5(self.url.encode()).hexdigest()[:16]
        return self.temp_dir / url_hash

    def init_cache(self) -> None:
        """初始化缓存目录"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"缓存目录已初始化：{self.cache_dir}")

    def save_master_m3u8(self, content: str) -> Path:
        """
        保存主 m3u8 列表文件

        Args:
            content: m3u8 文件内容

        Returns:
            保存的文件路径
        """
        self.init_cache()
        m3u8_path = self.cache_dir / self.MASTER_M3U8_FILENAME
        with open(m3u8_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.debug(f"主 m3u8 文件已保存：{m3u8_path}")
        return m3u8_path

    def load_master_m3u8(self) -> Optional[str]:
        """
        从缓存加载主 m3u8 文件内容

        Returns:
            m3u8 文件内容，如果不存在则返回 None
        """
        m3u8_path = self.cache_dir / self.MASTER_M3U8_FILENAME
        if m3u8_path.exists():
            with open(m3u8_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug(f"主 m3u8 文件已从缓存加载：{m3u8_path}")
            return content
        return None

    def master_m3u8_exists(self) -> bool:
        """
        检查主 m3u8 文件是否存在于缓存中

        Returns:
            是否存在
        """
        m3u8_path = self.cache_dir / self.MASTER_M3U8_FILENAME
        return m3u8_path.exists()

    def _get_resolution_filename(self, resolution: tuple[int, int]) -> str:
        """根据分辨率获取 m3u8 文件名"""
        height = resolution[1] if resolution else 0
        return self.RESOLUTION_M3U8_PATTERN.format(height)

    def save_resolution_m3u8(self, resolution: tuple[int, int], content: str) -> Path:
        """
        保存指定分辨率的 m3u8 文件

        Args:
            resolution: 分辨率 (宽度，高度)
            content: m3u8 文件内容

        Returns:
            保存的文件路径
        """
        self.init_cache()
        filename = self._get_resolution_filename(resolution)
        m3u8_path = self.cache_dir / filename
        with open(m3u8_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.debug(f"分辨率 m3u8 文件已保存：{m3u8_path}")
        return m3u8_path

    def load_resolution_m3u8(self, resolution: tuple[int, int]) -> Optional[str]:
        """
        从缓存加载指定分辨率的 m3u8 文件内容

        Args:
            resolution: 分辨率 (宽度，高度)

        Returns:
            m3u8 文件内容，如果不存在则返回 None
        """
        m3u8_path = self.cache_dir / self._get_resolution_filename(resolution)
        if m3u8_path.exists():
            with open(m3u8_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug(f"分辨率 m3u8 文件已从缓存加载：{m3u8_path}")
            return content
        return None

    def resolution_m3u8_exists(self, resolution: tuple[int, int]) -> bool:
        """
        检查指定分辨率的 m3u8 文件是否存在于缓存中

        Args:
            resolution: 分辨率 (宽度，高度)

        Returns:
            是否存在
        """
        m3u8_path = self.cache_dir / self._get_resolution_filename(resolution)
        return m3u8_path.exists()

    def get_segment_path(self, filename: str) -> Path:
        """
        获取分片文件的本地路径

        Args:
            filename: 分片文件名

        Returns:
            分片文件的完整路径
        """
        self.init_cache()
        return self.cache_dir / filename

    def segment_exists(self, filename: str) -> bool:
        """
        检查分片文件是否已存在

        Args:
            filename: 分片文件名

        Returns:
            是否存在
        """
        segment_path = self.get_segment_path(filename)
        return segment_path.exists()

    def save_segment(self, filename: str, content: bytes) -> Path:
        """
        保存分片文件

        Args:
            filename: 分片文件名
            content: 分片内容

        Returns:
            保存的文件路径
        """
        self.init_cache()
        segment_path = self.cache_dir / filename

        # 确保父目录存在（如果 filename 包含子目录）
        segment_path.parent.mkdir(parents=True, exist_ok=True)

        # 先写入临时文件，再重命名，确保原子性
        temp_path = segment_path.with_suffix(segment_path.suffix + ".tmp")
        with open(temp_path, "wb") as f:
            f.write(content)
        temp_path.rename(segment_path)

        logger.debug(f"分片已保存：{segment_path}")
        return segment_path

    def get_all_segments(self) -> list[Path]:
        """
        获取缓存目录中所有的分片文件

        Returns:
            分片文件路径列表
        """
        if not self.cache_dir.exists():
            return []

        valid_suffixes = {".ts", ".m4s", ".mp4"}
        segments = [
            f for f in self.cache_dir.iterdir()
            if f.is_file() and f.suffix in valid_suffixes and not f.name.endswith(".tmp")
        ]
        segments.sort(key=lambda p: p.name)
        return segments

    def get_all_m3u8_files(self) -> list[Path]:
        """
        获取缓存目录中所有的 m3u8 文件

        Returns:
            m3u8 文件路径列表
        """
        if not self.cache_dir.exists():
            return []

        return [f for f in self.cache_dir.iterdir() if f.is_file() and f.suffix == ".m3u8"]

    def clear_segments(self) -> bool:
        """
        清理已下载的分片文件，保留元数据和 m3u8 文件

        根据元数据中记录的文件列表删除分片，在合并完成后调用

        Returns:
            是否清理成功
        """
        if self.keep_cache:
            logger.info(f"保留缓存文件：{self.cache_dir}")
            return True

        if not self.cache_dir.exists():
            logger.debug("缓存目录不存在，无需清理")
            return True

        metadata = self.load_metadata()
        if not metadata:
            logger.warning("元数据不存在，无法清理分片文件")
            return False

        try:
            deleted_count = 0
            for filename in metadata.filenames:
                segment_path = self.cache_dir / filename
                if segment_path.exists():
                    segment_path.unlink()
                    deleted_count += 1

            logger.info(f"已清理 {deleted_count} 个分片文件，保留元数据和 m3u8 文件：{self.cache_dir}")
            return True
        except Exception as e:
            logger.error(f"清理分片文件失败：{e}")
            return False

    def clear_cache(self) -> bool:
        """
        删除整个缓存目录（包括分片、m3u8 文件和元数据）

        此函数不会被自动调用，需手动调用
        不受 keep_cache 标志影响，强制删除

        Returns:
            是否清理成功
        """
        if not self.cache_dir.exists():
            logger.debug("缓存目录不存在，无需清理")
            return True

        try:
            shutil.rmtree(self.cache_dir)
            logger.info(f"整个缓存目录已删除：{self.cache_dir}")
            return True
        except Exception as e:
            logger.error(f"清理缓存失败：{e}")
            return False

    def save_metadata(self, metadata: MetaData) -> Path:
        """
        保存元数据到缓存目录

        Args:
            metadata: 元数据对象

        Returns:
            保存的文件路径
        """
        self.init_cache()
        metadata_path = self.cache_dir / self.METADATA_FILENAME
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
        logger.debug(f"元数据已保存：{metadata_path}")
        return metadata_path

    def update_metadata_downloaded_mask(self) -> Optional[MetaData]:
        """
        更新元数据中的 downloaded_mask，根据实际缓存文件状态

        Returns:
            更新后的元数据对象，如果元数据不存在则返回 None
        """
        metadata = self.load_metadata()
        if not metadata:
            return None

        # 根据实际文件更新 mask
        new_mask = 0
        for i, filename in enumerate(metadata.filenames):
            if self.segment_exists(filename):
                new_mask |= (1 << i)

        metadata.downloaded_mask = new_mask

        # 保存更新后的元数据
        self.save_metadata(metadata)
        logger.debug(f"元数据 downloaded_mask 已更新：{bin(new_mask)}")
        return metadata

    def load_metadata(self) -> Optional[MetaData]:
        """
        从缓存目录加载元数据

        Returns:
            元数据对象，如果不存在则返回 None
        """
        metadata_path = self.cache_dir / self.METADATA_FILENAME
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            metadata = MetaData.from_dict(data)
            logger.debug(f"元数据已从缓存加载：{metadata_path}")
            return metadata
        except Exception as e:
            logger.warning(f"加载元数据失败：{e}")
            return None

    def metadata_exists(self) -> bool:
        """
        检查元数据文件是否存在于缓存中

        Returns:
            是否存在
        """
        metadata_path = self.cache_dir / self.METADATA_FILENAME
        return metadata_path.exists()

    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        if not self.cache_dir.exists():
            return {
                "exists": False,
                "path": str(self.cache_dir),
                "segment_count": 0,
                "m3u8_count": 0,
                "total_size": 0
            }

        segments = self.get_all_segments()
        m3u8_files = self.get_all_m3u8_files()
        total_size = sum(f.stat().st_size for f in self.cache_dir.iterdir() if f.is_file())

        return {
            "exists": True,
            "path": str(self.cache_dir),
            "segment_count": len(segments),
            "m3u8_count": len(m3u8_files),
            "total_size": total_size
        }

    @property
    def cache_path(self) -> Path:
        """获取缓存目录路径"""
        return self.cache_dir
