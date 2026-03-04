#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m3u8 解析模块
负责解析 m3u8 文件，提取分片信息
"""

from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.exceptions import RequestException

from models import AppConfig, SegmentInfo, ParseResult
from logger import get_logger

logger = get_logger("parser")


class M3u8Parser:
    """m3u8 解析器"""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.timeout = config.timeout
    
    def parse(self) -> ParseResult:
        """
        解析 m3u8 文件
        
        Returns:
            ParseResult: 解析结果
        """
        url = self.config.url
        logger.info(f"正在解析：{url}")
        
        try:
            response = requests.get(
                url, 
                headers=self.HEADERS, 
                timeout=self.timeout
            )
            response.raise_for_status()
        except RequestException as e:
            logger.error(f"无法获取 m3u8 文件 - {e}")
            return ParseResult(
                segments=[],
                base_url="",
                success=False,
                error=f"无法获取 m3u8 文件 - {e}"
            )
        
        content = response.text
        base_url = self._get_base_url(url)
        segments = self._extract_segments(content, base_url)
        
        if not segments:
            logger.error("未找到任何视频分片")
            return ParseResult(
                segments=[],
                base_url=base_url,
                success=False,
                error="未找到任何视频分片"
            )
        
        logger.info(f"解析成功，共找到 {len(segments)} 个分片")
        
        return ParseResult(
            segments=segments,
            base_url=base_url,
            success=True
        )
    
    def _get_base_url(self, url: str) -> str:
        """获取 URL 的基准路径"""
        parsed = urlparse(url)
        path = parsed.path
        
        if "/" in path:
            path = path.rsplit("/", 1)[0] + "/"
        
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    
    def _extract_segments(
        self, 
        content: str, 
        base_url: str
    ) -> list[SegmentInfo]:
        """
        从 m3u8 内容中提取分片
        
        Args:
            content: m3u8 文件内容
            base_url: 基准 URL
            
        Returns:
            分片信息列表
        """
        segments = []
        
        for line in content.splitlines():
            line = line.strip()
            
            # 跳过注释和空行
            if not line or line.startswith("#"):
                continue
            
            # 提取分片 URL
            if line.endswith(".ts") or line.endswith(".m4s"):
                segment_url = urljoin(base_url, line)
                filename = self._get_segment_filename(line, len(segments))
                
                segments.append(SegmentInfo(
                    url=segment_url,
                    index=len(segments),
                    filename=filename
                ))
        
        return segments
    
    def _get_segment_filename(
        self, 
        url_path: str, 
        index: int
    ) -> str:
        """
        生成分片文件名
        
        Args:
            url_path: URL 路径部分
            index: 分片索引
            
        Returns:
            文件名
        """
        parsed = urlparse(url_path)
        name = Path(parsed.path).name
        
        if name:
            return name
        return f"segment_{index:06d}.ts"
