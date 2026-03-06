# m3u8 下载器 - 前后端分离版本（异步架构）

本项目已将原始的 m3u8 下载器重构为前后端分离架构，采用异步实现。

> **完整 API 文档**: 详见 [API.md](API.md)

## 项目结构

```
m3u8-downloader/
├── backend/                  # 后端服务
│   ├── server.py            # Quart 异步 API 服务
│   ├── task_manager.py      # 任务管理器（后台任务管理）
│   ├── models.py            # 数据模型
│   ├── logger.py            # 日志模块
│   ├── cache_manager.py     # 缓存管理
│   ├── parser.py            # 异步 m3u8 解析
│   ├── downloader.py        # 异步分片下载
│   └── postprocessor.py     # 异步后处理 (ffmpeg 合并)
│
├── frontend/                # 前端 CLI
│   └── cli.py              # 命令行接口
│
├── start_server_async.py   # 启动异步后端服务
├── start_server.py         # 启动同步后端服务（兼容）
├── start_cli.py            # 启动前端 CLI
└── requirements.txt        # 依赖列表
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动异步后端服务

```bash
python start_server_async.py
```

后端服务默认监听 `127.0.0.1:5000`

可选参数：
- `--host`: 监听地址 IP (默认：127.0.0.1)
- `--port`: 监听端口 (默认：5000)
- `--default-threads`: 默认下载并发数 (默认：8)
- `--log-level`: 日志级别 DEBUG|INFO|WARNING|ERROR|CRITICAL (默认：INFO)
- `--log-dir`: 日志目录 (默认：logs)
- `--debug`: 启用调试模式（等同于 --log-level DEBUG）

示例：
```bash
# 监听所有地址，端口 8080
python start_server_async.py --host 0.0.0.0 --port 8080

# 设置默认 16 并发，DEBUG 日志
python start_server_async.py --default-threads 16 --log-level DEBUG

# 自定义日志目录
python start_server_async.py --log-dir /var/log/m3u8-downloader
```

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

### 4. 缓存管理

```bash
# 列出所有缓存
python start_cli.py cache list

# 删除指定缓存
python start_cli.py cache rm <cache_id>

# 清空所有缓存
python start_cli.py cache clear

# 更新缓存元数据
python start_cli.py cache update <m3u8_url>
```

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

### API 端点变化

异步版本新增以下端点：

| 端点 | 说明 |
|------|------|
| `POST /api/download` | 提交异步下载任务（立即返回 task_id） |
| `GET /api/tasks` | 列出所有任务 |
| `GET /api/tasks/<id>` | 查询任务状态/进度 |
| `DELETE /api/tasks/<id>` | 取消任务 |
| `POST /api/download/sync` | 同步下载（兼容旧 API） |

### 使用示例

```bash
# 1. 提交异步下载任务
curl -X POST http://127.0.0.1:5000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.m3u8"}'

# 返回: {"success": true, "task_id": "abc12345", "status": "pending"}

# 2. 查询任务进度
curl http://127.0.0.1:5000/api/tasks/abc12345

# 3. 取消任务
curl -X DELETE http://127.0.0.1:5000/api/tasks/abc12345
```

## 注意事项

1. 使用前请确保已安装 ffmpeg 并添加到 PATH
2. 后端服务需要保持运行才能使用 CLI 工具
3. 默认情况下，下载完成后会清理分片文件，保留元数据
