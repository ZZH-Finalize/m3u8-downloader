# m3u8 下载器

> **项目说明**: 本项目完全由 AI 开发，开发此项目的模型是 **Qwen Code**（阿里巴巴通义千问）。

一个基于异步架构的 m3u8 视频下载器，提供 RESTful API 后端服务和 Edge 浏览器插件前端。

## 项目结构

```
m3u8-downloader/
├── backend/                # 后端服务
│   ├── server.py          # Quart 异步 API 服务
│   ├── task_manager.py    # 任务管理器（后台任务管理）
│   ├── models.py          # 数据模型
│   ├── logger.py          # 日志模块
│   ├── cache_manager.py   # 缓存管理
│   ├── parser.py          # 异步 m3u8 解析
│   ├── downloader.py      # 异步分片下载
│   └── postprocessor.py   # 异步后处理 (ffmpeg 合并)
│
├── extension/              # Edge 浏览器插件（官方前端）
│   ├── manifest.json      # 插件配置文件
│   ├── popup.html         # 插件页面
│   ├── popup.js           # 逻辑脚本
│   └── icons/             # 图标文件
│
├── tools/                  # 工具目录
│   └── test_cli.py        # API 测试工具（开发调试用）
│
├── docker/                 # Docker 相关配置
├── requirements.txt       # 依赖列表
├── README_ARCH.md         # 服务端架构说明（本文件）
└── API.md                 # 完整 API 文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
python backend/server.py
```

后端服务默认监听 `127.0.0.1:6900`

可选参数：
- `--host`: 监听地址 IP (默认：127.0.0.1)
- `--port`: 监听端口 (默认：6900)
- `--default-threads`: 默认下载并发数 (默认：8)
- `--log-level`: 日志级别 DEBUG|INFO|WARNING|ERROR|CRITICAL (默认：INFO)
- `--log-dir`: 日志目录 (默认：logs)
- `--debug`: 启用调试模式（等同于 --log-level DEBUG）

示例：
```bash
# 监听所有地址，端口 8080
python backend/server.py --host 0.0.0.0 --port 8080

# 设置默认 16 并发，DEBUG 日志
python backend/server.py --default-threads 16 --log-level DEBUG
```

### 3. 使用 Edge 插件下载视频

1. 打开 Edge 浏览器，访问 `edge://extensions/`
2. 开启"开发人员模式"，点击"加载解压缩的扩展"
3. 选择 `extension` 文件夹加载插件
4. 确保后端服务已启动
5. 点击浏览器工具栏中的插件图标，提交下载任务

详细说明请查看 [extension/README.md](extension/README.md)。

## API 文档

完整的 API 文档请查看 [API.md](API.md)。

### 快速参考

#### 下载视频
```http
POST /api/download
```

#### 获取服务器配置
```http
GET /api/config
```

#### 缓存管理
```http
GET    /api/cache/list       # 列出所有缓存
GET    /api/cache/<id>       # 获取缓存详情
DELETE /api/cache/<id>       # 删除指定缓存
POST   /api/cache/clear      # 清空所有缓存
POST   /api/cache/update     # 更新缓存元数据
```

#### 健康检查
```http
GET /health
```

## 架构说明

### 异步架构设计

- **前台任务**：响应 API 请求（立即返回）
- **后台任务**：下载分片、转码等（异步执行）
- **任务管理器**：跟踪和管理所有后台任务

### 技术栈

- **后端框架**: Quart (Flask 的异步版本)
- **HTTP 客户端**: aiohttp (异步 HTTP)
- **任务管理**: asyncio 任务调度

### API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/download` | 提交异步下载任务（立即返回 task_id） |
| `GET /api/tasks` | 列出所有任务 |
| `GET /api/tasks/<id>` | 查询任务状态/进度 |
| `DELETE /api/tasks/<id>` | 取消任务 |

### 使用示例

```bash
# 1. 提交异步下载任务
curl -X POST http://127.0.0.1:6900/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.m3u8"}'

# 返回：{"success": true, "task_id": "abc12345", "status": "pending"}

# 2. 查询任务进度
curl http://127.0.0.1:6900/api/tasks/abc12345

# 3. 取消任务
curl -X DELETE http://127.0.0.1:6900/api/tasks/abc12345
```

## Docker 部署

### 环境变量配置

后端服务支持以下环境变量：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SERVER_HOST` | `0.0.0.0` | 监听地址 IP |
| `SERVER_PORT` | `6900` | 监听端口 |
| `DEFAULT_THREADS` | `8` | 默认下载并发数 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_DIR` | `logs` | 日志目录 |
| `DEBUG` | `false` | 启用调试模式 |
| `FFMPEG_PATH` | `ffmpeg` | ffmpeg 路径 |

### FFmpeg 配置

镜像**不自带 ffmpeg**，需要宿主机提供：

```yaml
volumes:
  - /usr/bin/ffmpeg:/usr/bin/ffmpeg:ro
environment:
  - FFMPEG_PATH=/usr/bin/ffmpeg
```

### 方式一：使用 Docker Compose（推荐）

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 方式二：使用 Docker 命令

```bash
# 构建镜像
docker build -t m3u8-downloader .

# 运行容器
docker run -d \
  --name m3u8-downloader \
  -p 6900:6900 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/logs:/app/logs \
  m3u8-downloader
```

### 目录挂载

| 容器路径 | 宿主机路径 | 说明 |
|----------|------------|------|
| `/app/downloads` | `./downloads` | 下载的视频文件 |
| `/app/logs` | `./logs` | 日志文件 |

### 健康检查

```bash
curl http://localhost:6900/health
```

## 注意事项

1. 使用前请确保已安装 ffmpeg 并添加到 PATH
2. 后端服务需要保持运行才能使用 Edge 插件
3. 默认情况下，下载完成后会清理分片文件，保留元数据
4. `tools/test_cli.py` 仅用于开发调试，生产环境请使用 Edge 插件

## 许可证

GNU General Public License v3.0 (GPL-3.0)
