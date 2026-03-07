# 异步重构总结

## 概述

已将 m3u8 下载器后端从同步 Flask 实现重构为异步 Quart 实现，实现了前台任务（API 响应）与后台任务（下载、转码）的分离。

**前端说明**: 
- **官方前端**: Edge 浏览器插件（位于 `extension/` 目录）
- **测试工具**: `tools/test_cli.py`（仅用于开发调试）

## 架构变更

### 之前（同步架构）
```
客户端请求 → Flask 同步处理 → 等待下载完成 → 返回结果
```
- 缺点：API 请求会阻塞，长时间任务导致连接超时

### 之后（异步架构）
```
客户端请求 → Quart 立即返回 task_id → 后台异步执行任务 → 客户端查询进度
```
- 优点：API 立即响应，后台任务异步执行，支持进度查询和任务取消

## 新增文件

| 文件 | 说明 |
|------|------|
| `backend/parser.py` | 异步 m3u8 解析器（使用 aiohttp） |
| `backend/downloader.py` | 异步分片下载器（使用 aiohttp + asyncio） |
| `backend/postprocessor.py` | 异步后处理器（使用 asyncio subprocess） |
| `backend/task_manager.py` | 任务管理器（管理后台任务生命周期） |
| `requirements.txt` | 项目依赖 |

## 删除文件

| 文件 | 说明 |
|------|------|
| `backend/parser.py` (旧) | 同步 m3u8 解析器 |
| `backend/downloader.py` (旧) | 同步分片下载器 |
| `backend/postprocessor.py` (旧) | 同步后处理器 |

## 修改文件

| 文件 | 变更 |
|------|------|
| `backend/server.py` | 从 Flask 改为 Quart，实现异步 API |
| `README_ARCH.md` | 更新架构说明 |
| `API.md` | 添加异步 API 端点文档 |

## API 端点变化

### 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/download` | POST | 提交异步下载任务（返回 task_id） |
| `/api/tasks` | GET | 列出所有任务 |
| `/api/tasks/<id>` | GET | 查询任务状态/进度 |
| `/api/tasks/<id>` | DELETE | 取消任务 |
| `/api/download/sync` | POST | 同步下载（兼容旧 API） |

### 保留端点

所有原有端点保持不变：
- `/health` - 健康检查
- `/api/config` - 服务器配置
- `/api/cache/*` - 缓存管理

## 技术栈变更

| 组件 | 之前 | 之后 |
|------|------|------|
| Web 框架 | Flask | Quart |
| HTTP 客户端 | requests | aiohttp |
| 并发模型 | 多线程 | asyncio |
| 任务管理 | 无 | TaskManager |
| 解析器 | 同步 | 异步 M3u8Parser |
| 下载器 | 同步 | 异步 SegmentDownloader |
| 后处理器 | 同步 | 异步 MediaPostprocessor |

## 使用示例

### 1. 启动异步服务

```bash
python backend/server.py --host 0.0.0.0 --port 8080
```

### 2. 提交下载任务

```bash
curl -X POST http://localhost:8080/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.m3u8"}'
```

响应：
```json
{
  "success": true,
  "task_id": "abc12345",
  "status": "pending",
  "message": "任务已提交，后台执行中"
}
```

### 3. 查询任务进度

```bash
curl http://localhost:8080/api/tasks/abc12345
```

响应：
```json
{
  "success": true,
  "task_id": "abc12345",
  "progress": {
    "status": "downloading",
    "progress_percent": 45.5,
    "segments_downloaded": 45,
    "total_segments": 100
  }
}
```

### 4. 取消任务

```bash
curl -X DELETE http://localhost:8080/api/tasks/abc12345
```

## 任务状态流转

```
pending → parsing → downloading → merging → completed
                              ↓
                        failed/cancelled
```

## 性能优势

1. **高并发**: 使用 aiohttp 异步 HTTP 客户端，支持更高的并发下载
2. **非阻塞**: API 请求立即响应，不会因长时间任务而阻塞
3. **资源效率**: 异步 IO 减少线程切换开销
4. **可取消**: 支持任务取消，节省资源

## 兼容性

- 保留同步下载端点 `/api/download/sync` 用于兼容旧客户端
- 所有缓存管理 API 保持不变
- 同步版本的模块已删除，全部替换为异步实现

## 注意事项

1. 需要安装 Quart 和 aiohttp：`pip install -r requirements.txt`
2. 确保 ffmpeg 可用（用于合并分片）
3. 任务完成后可以通过 `/api/tasks/<id>` 查询结果
4. 已结束的任务可以通过 `DELETE /api/tasks/<id>` 移除

## 后续优化建议

1. 添加任务持久化（重启后恢复任务）
2. 添加任务队列和优先级
3. 添加并发任务数限制
4. 添加 WebSocket 支持（实时推送进度）
