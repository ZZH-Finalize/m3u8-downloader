#!/usr/bin/env python3
"""
生成 m3u8 下载器插件的占位图标
使用 PIL/Pillow 库创建简单的 PNG 图标
"""

import os
import struct
import zlib

def create_png(width, height, pixels):
    """创建 PNG 文件"""
    def png_chunk(chunk_type, data):
        chunk_len = struct.pack('>I', len(data))
        chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
        return chunk_len + chunk_type + data + chunk_crc
    
    # PNG 签名
    signature = b'\x89PNG\r\n\x1a\n'
    
    # IHDR 块
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)
    
    # IDAT 块（图像数据）
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # 过滤器类型：None
        for x in range(width):
            raw_data += bytes(pixels[x, y])
    
    compressed = zlib.compress(raw_data, 9)
    idat = png_chunk(b'IDAT', compressed)
    
    # IEND 块
    iend = png_chunk(b'IEND', b'')
    
    return signature + ihdr + idat + iend

def create_icon(size):
    """创建图标像素"""
    pixels = {}
    cx, cy = size // 2, size // 2
    radius = int(size * 0.45)
    radius_sq = radius * radius
    
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist_sq = dx * dx + dy * dy
            
            if dist_sq <= radius_sq:
                # 渐变背景（紫色）
                t = (dy + radius) / (2 * radius)
                r = int(102 + t * (118 - 102))
                g = int(126 + t * (75 - 126))
                b = int(234 + t * (162 - 234))
                pixels[x, y] = (r, g, b)
            else:
                pixels[x, y] = (0, 0, 0, 0) if size > 16 else (255, 255, 255)
    
    # 绘制播放三角形（白色）
    tri_size = int(size * 0.15)
    for y in range(cy - tri_size, cy + tri_size):
        for x in range(cx - int(tri_size * 0.8), cx + int(tri_size * 0.6)):
            # 简单的三角形填充
            left_edge = cx - int(tri_size * 0.8)
            right_edge = cx + int(tri_size * 0.6) * (y - (cy - tri_size)) / (2 * tri_size)
            if cy - tri_size < y < cy + tri_size and left_edge < x < cx - int(tri_size * 0.2) + (y - cy) * 0.5:
                if (x, y) in pixels:
                    pixels[x, y] = (255, 255, 255)
    
    return pixels

def create_simple_icon(size):
    """创建简化版图标（纯色圆形）"""
    pixels = {}
    cx, cy = size // 2, size // 2
    radius = int(size * 0.45)
    radius_sq = radius * radius
    
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist_sq = dx * dx + dy * dy
            
            if dist_sq <= radius_sq:
                # 紫色渐变
                t = (dy + radius) / (2 * radius)
                r = int(102 + t * (118 - 102))
                g = int(126 + t * (75 - 126))
                b = int(234 + t * (162 - 234))
                pixels[x, y] = (r, g, b)
            else:
                pixels[x, y] = (0, 0, 0, 0)
    
    return pixels

def create_icon_with_download_symbol(size):
    """创建带下载符号的图标"""
    pixels = create_simple_icon(size)
    cx, cy = size // 2, size // 2
    
    # 绘制向下的箭头（白色）
    arrow_top = cy + int(size * 0.05)
    arrow_bottom = cy + int(size * 0.25)
    arrow_width = int(size * 0.08)
    
    # 箭头竖线
    for y in range(arrow_top, arrow_bottom):
        for x in range(cx - arrow_width, cx + arrow_width + 1):
            if (x, y) in pixels:
                pixels[x, y] = (255, 255, 255)
    
    # 箭头头部 V 形
    for i in range(int(size * 0.06)):
        for j in range(int(size * 0.04)):
            x1, y1 = cx - int(size * 0.04) + i, arrow_bottom + i + j
            x2, y2 = cx + int(size * 0.04) - i, arrow_bottom + i + j
            if (x1, y1) in pixels:
                pixels[x1, y1] = (255, 255, 255)
            if (x2, y2) in pixels:
                pixels[x2, y2] = (255, 255, 255)
    
    return pixels

def main():
    icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
    os.makedirs(icons_dir, exist_ok=True)
    
    sizes = [16, 48, 128]
    
    print('正在生成图标...')
    for size in sizes:
        pixels = create_icon_with_download_symbol(size)
        png_data = create_png(size, size, pixels)
        
        filepath = os.path.join(icons_dir, f'icon{size}.png')
        with open(filepath, 'wb') as f:
            f.write(png_data)
        
        print(f'[OK] 已生成：icon{size}.png ({size}x{size})')
    
    print('\n图标生成完成！')

if __name__ == '__main__':
    main()
