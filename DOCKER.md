# Docker 部署指南

本文档说明如何使用 Docker 部署 m3u8 下载器后端服务。

## 环境变量配置

后端服务支持以下环境变量：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SERVER_HOST` | `0.0.0.0` | 监听地址 IP |
| `SERVER_PORT` | `5000` | 监听端口 |
| `DEFAULT_THREADS` | `8` | 默认下载并发数 |
| `LOG_LEVEL` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `LOG_DIR` | `logs` | 日志目录 |
| `DEBUG` | `false` | 启用调试模式（等同于 --log-level DEBUG） |
| `FFMPEG_PATH` | `ffmpeg` | ffmpeg 路径（可通过挂载宿主机 ffmpeg 或设置完整路径） |

## FFmpeg 配置

镜像**不自带 ffmpeg**，需要宿主机提供。有以下使用方式：

### 方式 1：使用宿主机的 ffmpeg（推荐）

通过挂载卷将宿主机的 ffmpeg 映射到容器内：

```yaml
volumes:
  - /usr/bin/ffmpeg:/usr/bin/ffmpeg:ro
environment:
  - FFMPEG_PATH=/usr/bin/ffmpeg
```

### 方式 2：使用 PATH 中的 ffmpeg

如果容器内 PATH 环境变量已包含 ffmpeg 路径，可直接使用默认值：

```yaml
environment:
  - FFMPEG_PATH=ffmpeg
```

### 方式 3：指定 ffmpeg 完整路径

```yaml
environment:
  - FFMPEG_PATH=/opt/ffmpeg/ffmpeg
```

## 方式一：使用 Docker Compose（推荐）

### 1. 构建并启动

```bash
docker-compose up -d --build
```

### 2. 查看日志

```bash
docker-compose logs -f
```

### 3. 停止服务

```bash
docker-compose down
```

### 4. 修改配置

编辑 `docker-compose.yml` 中的 `environment` 部分，然后重启：

```bash
docker-compose up -d
```

## 方式二：使用 Docker 命令

### 1. 构建镜像

```bash
docker build -t m3u8-downloader .
```

### 2. 运行容器（默认配置）

```bash
docker run -d \
  --name m3u8-downloader \
  -p 5000:5000 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/logs:/app/logs \
  m3u8-downloader
```

### 3. 运行容器（自定义配置）

```bash
docker run -d \
  --name m3u8-downloader \
  -p 5000:5000 \
  -e SERVER_HOST=0.0.0.0 \
  -e SERVER_PORT=5000 \
  -e DEFAULT_THREADS=16 \
  -e LOG_LEVEL=DEBUG \
  -e LOG_DIR=logs \
  -e DEBUG=false \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/logs:/app/logs \
  m3u8-downloader
```

### 4. 停止并删除容器

```bash
docker stop m3u8-downloader
docker rm m3u8-downloader
```

## 配置示例

### 示例 1：高并发下载

```yaml
environment:
  - DEFAULT_THREADS=32
  - LOG_LEVEL=INFO
```

### 示例 2：调试模式

```yaml
environment:
  - DEBUG=true
  - LOG_LEVEL=DEBUG
```

### 示例 3：自定义端口

```yaml
ports:
  - "8080:5000"
environment:
  - SERVER_PORT=5000
```

## 目录挂载

| 容器路径 | 宿主机路径 | 说明 |
|----------|------------|------|
| `/app/downloads` | `./downloads` | 下载的视频文件 |
| `/app/logs` | `./logs` | 日志文件 |

## 健康检查

服务内置健康检查端点 `/health`，可通过以下方式检查状态：

```bash
curl http://localhost:5000/health
```

响应示例：
```json
{
    "status": "healthy",
    "service": "m3u8-downloader-api",
    "async": true
}
```

## 常见问题

### 1. 容器启动失败

检查日志：
```bash
docker-compose logs
```

### 2. 权限问题（Linux/Mac）

如果遇到挂载目录权限问题：
```bash
sudo chown -R $(whoami):$(whoami) ./downloads ./logs
```

### 3. 端口被占用

修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8080:5000"  # 将 8080 改为其他未占用端口
```

### 4. 重新构建镜像

```bash
docker-compose build --no-cache
```

## API 访问

服务启动后，API 端点为：`http://localhost:5000`

示例请求：
```bash
# 健康检查
curl http://localhost:5000/health

# 提交下载任务
curl -X POST http://localhost:5000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.m3u8"}'

# 查看配置
curl http://localhost:5000/api/config
```
