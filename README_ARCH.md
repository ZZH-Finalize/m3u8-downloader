# m3u8 下载器 - 前后端分离版本

本项目已将原始的 m3u8 下载器重构为前后端分离架构。

## 项目结构

```
m3u8-downloader/
├── backend/              # 后端服务
│   ├── server.py        # Flask API 服务
│   ├── models.py        # 数据模型
│   ├── logger.py        # 日志模块
│   ├── cache_manager.py # 缓存管理
│   ├── parser.py        # m3u8 解析
│   ├── downloader.py    # 分片下载
│   └── postprocessor.py # 后处理 (ffmpeg 合并)
│
├── frontend/            # 前端 CLI
│   └── cli.py          # 命令行接口
│
├── start_server.py     # 启动后端服务
├── start_cli.py        # 启动前端 CLI
└── requirements.txt    # 依赖列表
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
python start_server.py
```

后端服务默认监听 `127.0.0.1:5000`

可选参数：
- `--host`: 监听地址 (默认：127.0.0.1)
- `--port`: 监听端口 (默认：5000)
- `--debug`: 启用 Flask 调试模式

### 3. 使用前端 CLI 下载视频

```bash
python start_cli.py download <m3u8_url>
```

示例：
```bash
# 基本下载
python start_cli.py download https://example.com/video.m3u8

# 使用 8 个线程
python start_cli.py download https://example.com/video.m3u8 -j 8

# 指定输出文件名
python start_cli.py download https://example.com/video.m3u8 --output my_video.mp4

# 连接到远程 API 服务
python start_cli.py download https://example.com/video.m3u8 --api-host 192.168.1.100 --api-port 5000
```

## API 文档

### 健康检查
```
GET /health
```

### 下载视频
```
POST /api/download
```

请求体：
```json
{
    "url": "https://example.com/video.m3u8",
    "threads": 4,
    "output": "video.mp4",
    "max_rounds": 5,
    "keep_cache": false,
    "debug": false
}
```

响应：
```json
{
    "success": true,
    "output_path": "output/abc123/video.mp4",
    "segments_downloaded": 100,
    "total_segments": 100
}
```

## 架构说明

- **后端**: 提供 RESTful API，封装了所有下载、缓存管理和后处理逻辑
- **前端**: 负责命令行参数解析，通过 HTTP 请求调用后端 API
- **通信**: 前后端通过 HTTP/REST 进行通信

## 注意事项

1. 使用前请确保已安装 ffmpeg 并添加到 PATH
2. 后端服务需要保持运行才能使用 CLI 工具
3. 默认情况下，下载完成后会清理分片文件，保留元数据
