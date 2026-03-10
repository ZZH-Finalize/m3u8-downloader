# m3u8 下载器 - Docker 镜像

[![GitHub](https://img.shields.io/badge/GitHub-m3u8--downloader-blue?logo=github)](https://github.com/ZZH-Finalize/m3u8-downloader)
[![Docker](https://img.shields.io/badge/Docker-Hub-blue?logo=docker)](https://hub.docker.com/r/zzhfinalize/m3u8-download-server)

一个基于异步架构的 m3u8 视频下载器 Docker 镜像，提供 RESTful API 服务。

## 项目特点

- 🚀 **异步架构**：基于 Quart 和 aiohttp，高性能并发下载
- 📦 **开箱即用**：镜像已内置 ffmpeg，无需额外配置
- 🔧 **RESTful API**：完整的 API 接口，支持任务管理和缓存控制
- 🐳 **Docker 优化**：轻量级镜像，支持健康检查和环境变量配置

## 快速开始

### 1. Docker Compose 部署（推荐）

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  m3u8-downloader:
    image: zzhfinalize/m3u8-download-server:latest
    container_name: m3u8-downloader
    ports:
      - "6900:6900"
    volumes:
      - ./output:/output
      - ./data:/data
    environment:
      - SERVER_HOST=0.0.0.0
      - SERVER_PORT=6900
      - DEFAULT_THREADS=8
      - LOG_LEVEL=INFO
      - DEBUG=false
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:6900/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
```

启动服务：

```bash
# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 2. Docker 命令部署

```bash
docker run -d \
  --name m3u8-downloader \
  -p 6900:6900 \
  -v $(pwd)/output:/output \
  -v $(pwd)/data:/data \
  -e SERVER_HOST=0.0.0.0 \
  -e DEFAULT_THREADS=8 \
  -e LOG_LEVEL=INFO \
  --restart unless-stopped \
  zzhfinalize/m3u8-download-server:latest
```

## 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SERVER_HOST` | `0.0.0.0` | 监听地址 IP |
| `SERVER_PORT` | `6900` | 监听端口 |
| `DEFAULT_THREADS` | `8` | 默认下载并发数 |
| `LOG_LEVEL` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `LOG_DIR` | `/data/logs` | 日志目录 |
| `DEBUG` | `false` | 启用调试模式 |
| `TEMP_DIR` | `/data/temp_segments` | 临时分片目录 |
| `OUTPUT_DIR` | `/output` | 输出目录 |

## 目录挂载说明

| 容器路径 | 宿主机路径 | 说明 |
|----------|------------|------|
| `/output` | `./output` | 下载完成的视频文件 |
| `/data` | `./data` | 日志 (`/data/logs`) 和临时分片 (`/data/temp_segments`) |

### 使用 Edge 插件

本项目提供 Edge 浏览器插件前端

![plugin](https://raw.githubusercontent.com/ZZH-Finalize/m3u8-downloader/refs/heads/master/imgs/main-page.png)

打包好的插件可以在[https://github.com/ZZH-Finalize/m3u8-downloader/releases](https://github.com/ZZH-Finalize/m3u8-downloader/releases)下载到。

## API 简介

提交异步下载任务，立即返回 `task_id`，后台异步执行。

**请求**
```bash
# 提交下载任务
curl -X POST http://localhost:6900/api/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/video.m3u8",
    "threads": 8,
    "output": "my_video.mp4"
  }'
```

**成功响应**
```json
{
    "success": true,
    "task_id": "abc12345",
    "status": "pending",
    "message": "任务已提交，后台执行中"
}
```

**说明**
- 该接口是异步接口，提交任务后立即返回 `task_id`
- 使用返回的 `task_id` 可通过 `/api/tasks/<task_id>` 查询进度
- `task_id` 是 URL 的 MD5 哈希值（前 16 位字符）

其余完整的 API 文档请查看项目中的 [API.md](https://github.com/ZZH-Finalize/m3u8-downloader/blob/master/API.md) 文件。

## 使用示例

### 下载视频并跟踪进度

```bash
# 提交任务并获取 task_id
TASK_ID=$(curl -s -X POST http://localhost:6900/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.m3u8"}' | jq -r '.task_id')

# 轮询查询进度
while true; do
  STATUS=$(curl -s http://localhost:6900/api/tasks/$TASK_ID | jq -r '.progress.status')
  PROGRESS=$(curl -s http://localhost:6900/api/tasks/$TASK_ID | jq -r '.progress.progress_percent')
  echo "进度：$PROGRESS% 状态：$STATUS"
  [ "$STATUS" = "completed" ] && break
  sleep 2
done
```

## 注意事项

1. Docker 镜像已内置 ffmpeg，无需额外安装
2. 后端服务需要保持运行才能使用 Edge 插件
3. 默认情况下，下载完成后会清理分片文件，保留元数据
4. 完整的 API 文档请查看 [API.md](https://github.com/ZZH-Finalize/m3u8-downloader/blob/master/API.md)

## 相关资源

- **GitHub 仓库**: https://github.com/ZZH-Finalize/m3u8-downloader
- **Docker Hub**: https://hub.docker.com/r/zzhfinalize/m3u8-download-server
- **完整 API 文档**: https://github.com/ZZH-Finalize/m3u8-downloader/blob/master/API.md

## 许可证

GNU General Public License v3.0 (GPL-3.0)
