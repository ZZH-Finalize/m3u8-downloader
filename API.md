# m3u8 下载器 - API 文档（异步版本）

本文档详细说明了 m3u8 下载器后端服务提供的所有 RESTful API 端点。

## 基本信息

- **基础 URL**: `http://<host>:<port>`
- **默认地址**: `http://127.0.0.1:6900`
- **数据格式**: JSON
- **字符编码**: UTF-8

## 启动参数

启动后端服务时可配置以下参数：

```bash
python backend/server.py [选项]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `127.0.0.1` | 监听地址 IP |
| `--port` | `6900` | 监听端口 |
| `--max-threads` | `32` | 下载并发数上限。如果 API 请求传入的 threads 值大于此值，将使用此值。 |
| `--log-level` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `--log-dir` | `logs` | 日志目录 |
| `--debug` | - | 启用调试模式（等同于 --log-level DEBUG） |
| `--temp-dir` | `data/temp_segments` | 临时分片目录 |
| `--output-dir` | `output` | 输出目录 |

---

## API 端点概览

### 下载任务 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/download` | POST | 提交异步下载任务 |

### 任务管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/tasks` | GET | 列出所有任务 |
| `/api/tasks/<id>` | GET | 查询任务状态 |
| `/api/tasks/<id>` | DELETE | 删除任务（运行中则先取消再删除，已结束则直接删除） |

### 缓存管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cache/list` | GET | 列出所有缓存 |
| `/api/cache/<id>` | GET | 获取缓存详情 |
| `/api/cache/<id>` | DELETE | 删除指定缓存（如果缓存被任务引用则拒绝删除） |
| `/api/cache/clear` | POST | 清空所有缓存（跳过正在被任务引用的缓存） |
| `/api/cache/update` | POST | 更新缓存元数据 |

### 系统 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/config` | GET | 获取服务器配置 |

---

## API 端点

### 1. 健康检查

检查服务是否正常运行。

**请求**
```http
GET /health
```

**响应**
```json
{
    "status": "healthy",
    "service": "m3u8-downloader-api",
    "async": true
}
```

**状态码**
- `200 OK`: 服务正常

---

### 2. 获取服务器配置

获取当前服务器的配置信息。

**请求**
```http
GET /api/config
```

**响应**
```json
{
    "max_threads": 32,
    "log_level": "INFO",
    "log_dir": "logs"
}
```

**字段说明**
| 字段 | 类型 | 说明 |
|------|------|------|
| `max_threads` | int | 下载并发数上限 |
| `log_level` | string | 当前日志级别 |
| `log_dir` | string | 日志目录路径 |

---

### 3. 提交异步下载任务

提交下载任务，立即返回 task_id，后台异步执行。

**请求**
```http
POST /api/download
Content-Type: application/json
```

**请求体**
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

**请求参数**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | 是 | - | m3u8 文件的 URL |
| `threads` | int | 否 | `max-threads` | 下载并发数（如果大于 `max-threads`，则使用 `max-threads`） |
| `output` | string | 否 | `"video.mp4"` | 输出文件名 |
| `max_rounds` | int | 否 | `5` | 最大下载轮次（重试次数） |
| `keep_cache` | boolean | 否 | `false` | 是否保留缓存文件 |
| `debug` | boolean | 否 | `false` | 是否启用调试日志 |

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
- 该接口是异步接口，提交任务后立即返回
- 使用返回的 `task_id` 可通过 `/api/tasks/<task_id>` 查询进度
- 下载过程包括：解析 m3u8、下载分片、合并为 MP4、清理分片
- **注意**: `task_id` 是 URL 的 MD5 哈希值（前 16 位字符），与 `cache_id` 一致
  - 同一 URL 多次提交下载请求时，会复用同一个 task_id
  - 如果任务正在运行中，返回 "任务已存在且正在运行" 错误
  - 如果任务已完成，返回 "任务已完成"，不会重复下载
  - 如果任务失败或取消，会自动重启任务（重试逻辑）

**状态码**
- `200 OK`: 请求成功
- `400 Bad Request`: 参数错误
- `409 Conflict`: 任务已存在且正在运行
- `500 Internal Server Error`: 服务器错误

---

### 4. 列出所有任务

获取所有任务的列表。

**请求**
```http
GET /api/tasks
```

**响应**
```json
{
    "success": true,
    "tasks": [
        {
            "task_id": "abc12345",
            "segments_downloaded": 45,
            "total_segments": 100,
            "output_name": "video.mp4"
        },
        {
            "task_id": "def67890",
            "segments_downloaded": 100,
            "total_segments": 100,
            "output_name": "movie.mp4"
        }
    ],
    "total_count": 2
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `tasks` | array | 任务列表 |
| `tasks[].task_id` | string | 任务 ID |
| `tasks[].segments_downloaded` | int | 已下载分片数 |
| `tasks[].total_segments` | int | 总分片数 |
| `tasks[].output_name` | string | 输出文件名 |
| `total_count` | int | 任务总数 |

**状态码**
- `200 OK`: 成功

---

### 5. 查询任务状态

获取指定任务的当前状态和进度。

**请求**
```http
GET /api/tasks/<task_id>
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID（提交下载任务时返回） |

**响应**
```json
{
    "success": true,
    "task_id": "abc12345",
    "url": "https://example.com/video.m3u8",
    "output_name": "video.mp4",
    "progress": {
        "status": "downloading",
        "progress_percent": 45.5,
        "current_step": "下载分片中...",
        "segments_downloaded": 45,
        "total_segments": 100,
        "error": null,
        "result": null,
        "created_at": "2024-01-01T12:00:00",
        "started_at": "2024-01-01T12:00:01",
        "completed_at": null
    }
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `task_id` | string | 任务 ID |
| `url` | string | 原始 m3u8 URL |
| `output_name` | string | 输出文件名 |
| `progress` | object | 任务进度信息 |
| `progress.status` | string | 任务状态 (pending/parsing/downloading/merging/completed/failed/cancelled) |
| `progress.progress_percent` | float | 进度百分比 (0-100) |
| `progress.current_step` | string | 当前步骤描述 |
| `progress.segments_downloaded` | int | 已下载分片数 |
| `progress.total_segments` | int | 总分片数 |
| `progress.error` | string | 错误信息（失败时） |
| `progress.result` | object | 最终结果（完成时） |
| `progress.created_at` | string | 任务创建时间 |
| `progress.started_at` | string | 任务开始时间 |
| `progress.completed_at` | string | 任务完成时间 |

**状态码**
- `200 OK`: 成功
- `404 Not Found`: 任务不存在

---

### 6. 删除任务

删除任务。如果任务正在运行中，会先取消任务再删除；如果任务已结束（完成/失败/取消），则直接删除。

**请求**
```http
DELETE /api/tasks/<task_id>
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |

**成功响应（删除运行中的任务）**
```json
{
    "success": true,
    "message": "任务已删除：abc12345"
}
```

**成功响应（删除已结束的任务）**
```json
{
    "success": true,
    "message": "任务已删除：abc12345"
}
```

**失败响应**
```json
{
    "success": false,
    "error": "任务不存在"
}
```

**状态码**
- `200 OK`: 删除成功
- `404 Not Found`: 任务不存在

---

### 7. 列出所有缓存

获取所有缓存的视频信息。

**请求**
```http
GET /api/cache/list
```

**响应**
```json
{
    "success": true,
    "caches": [
        {
            "id": "74a993fffd15ddbe",
            "url": "https://example.com/video.m3u8",
            "segment_count": 100,
            "m3u8_count": 2,
            "total_size": 10485760,
            "total_size_mb": 10.0,
            "created_at": "2024-01-01T12:00:00"
        }
    ],
    "total_count": 1
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `caches` | array | 缓存列表 |
| `caches[].id` | string | 缓存 ID（URL 的 MD5 哈希） |
| `caches[].url` | string | 原始 m3u8 URL |
| `caches[].segment_count` | int | 分片数量 |
| `caches[].m3u8_count` | int | m3u8 文件数量 |
| `caches[].total_size` | int | 总大小（字节） |
| `caches[].total_size_mb` | float | 总大小（MB） |
| `caches[].created_at` | string | 创建时间（ISO 8601） |
| `total_count` | int | 缓存总数 |

**状态码**
- `200 OK`: 成功

---

### 8. 获取缓存详情

获取指定缓存的详细信息。

**请求**
```http
GET /api/cache/<cache_id>
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| `cache_id` | string | 缓存 ID |

**响应**
```json
{
    "success": true,
    "cache": {
        "id": "74a993fffd15ddbe",
        "url": "https://example.com/video.m3u8",
        "base_url": "https://example.com/video/",
        "segment_count": 100,
        "m3u8_count": 2,
        "total_size": 10485760,
        "total_size_mb": 10.0,
        "created_at": "2024-01-01T12:00:00",
        "downloaded_count": 80,
        "is_complete": false
    }
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 缓存 ID |
| `url` | string | 原始 m3u8 URL |
| `base_url` | string | 基准 URL |
| `segment_count` | int | 分片数量 |
| `m3u8_count` | int | m3u8 文件数量 |
| `total_size_mb` | float | 总大小（MB） |
| `created_at` | string | 创建时间 |
| `downloaded_count` | int | 已下载分片数 |
| `is_complete` | boolean | 是否全部下载完成 |

**状态码**
- `200 OK`: 成功
- `404 Not Found`: 缓存不存在

---

### 9. 删除指定缓存

删除单个缓存及其所有文件。如果缓存正在被任务列表中的任务引用，则拒绝删除。

**请求**
```http
DELETE /api/cache/<cache_id>
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| `cache_id` | string | 缓存 ID |

**成功响应**
```json
{
    "success": true,
    "message": "缓存已删除：74a993fffd15ddbe"
}
```

**失败响应（缓存不存在）**
```json
{
    "success": false,
    "error": "缓存不存在：74a993fffd15ddbe"
}
```

**失败响应（缓存被任务引用）**
```json
{
    "success": false,
    "error": "缓存 74a993fffd15ddbe 正在被任务列表中的任务使用，无法删除",
    "code": "CACHE_IN_USE"
}
```

**状态码**
- `200 OK`: 删除成功
- `404 Not Found`: 缓存不存在
- `409 Conflict`: 缓存正在被任务引用
- `500 Internal Server Error`: 删除失败

---

### 10. 清空所有缓存

删除所有缓存，但会跳过正在被任务列表中的任务引用的缓存。

**请求**
```http
POST /api/cache/clear
```

**响应**
```json
{
    "success": true,
    "deleted_count": 3,
    "skipped_count": 2,
    "message": "已删除 3 个缓存，跳过 2 个（任务引用中）"
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `deleted_count` | int | 删除的缓存数量 |
| `skipped_count` | int | 跳过的缓存数量（因任务引用） |
| `message` | string | 结果消息 |

**状态码**
- `200 OK`: 成功

---

### 11. 更新缓存元数据

重新下载 m3u8 文件并更新缓存元数据。

**请求**
```http
POST /api/cache/update
Content-Type: application/json
```

**请求体**
```json
{
    "url": "https://example.com/video.m3u8"
}
```

**请求参数**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | m3u8 文件的 URL |

**成功响应**
```json
{
    "success": true,
    "segment_count": 100,
    "message": "缓存元数据更新完成"
}
```

**失败响应**
```json
{
    "success": false,
    "error": "解析失败：无法获取 m3u8 文件"
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `segment_count` | int | 分片数量 |
| `message` | string | 结果消息 |
| `error` | string | 错误信息 |

**状态码**
- `200 OK`: 更新成功
- `400 Bad Request`: 参数错误
- `500 Internal Server Error`: 更新失败

---

## 错误响应格式

所有 API 错误都使用统一的响应格式：

```json
{
    "success": false,
    "error": "错误描述信息"
}
```

### 常见错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| `400 Bad Request` | 请求参数错误或缺少必要参数 |
| `404 Not Found` | 资源不存在（如缓存不存在、任务不存在） |
| `500 Internal Server Error` | 服务器内部错误 |

---

## 使用示例

### 使用 curl 调用

#### 1. 健康检查
```bash
curl http://127.0.0.1:6900/health
```

#### 2. 下载视频
```bash
curl -X POST http://127.0.0.1:6900/api/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/video.m3u8",
    "threads": 8,
    "output": "my_video.mp4"
  }'
```

使用测试工具进行进度跟踪：
```bash
python tools/test_cli.py download https://example.com/video.m3u8 --trace
```

#### 3. 列出所有任务
```bash
curl http://127.0.0.1:6900/api/tasks
```

#### 4. 查询任务状态
```bash
curl http://127.0.0.1:6900/api/tasks/abc12345
```

#### 5. 删除任务
```bash
curl -X DELETE http://127.0.0.1:6900/api/tasks/abc12345
```

#### 6. 列出缓存
```bash
curl http://127.0.0.1:6900/api/cache/list
```

#### 7. 获取缓存详情
```bash
curl http://127.0.0.1:6900/api/cache/74a993fffd15ddbe
```

#### 8. 删除缓存
```bash
curl -X DELETE http://127.0.0.1:6900/api/cache/74a993fffd15ddbe
```

#### 9. 清空所有缓存
```bash
curl -X POST http://127.0.0.1:6900/api/cache/clear
```

#### 10. 更新缓存元数据
```bash
curl -X POST http://127.0.0.1:6900/api/cache/update \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.m3u8"}'
```

#### 11. 获取服务器配置
```bash
curl http://127.0.0.1:6900/api/config
```

### 使用 Python 调用

```python
import requests

API_BASE = "http://127.0.0.1:6900"

# 下载视频（异步）
response = requests.post(f"{API_BASE}/api/download", json={
    "url": "https://example.com/video.m3u8",
    "threads": 8,
    "output": "my_video.mp4"
})
result = response.json()
task_id = result["task_id"]
print(f"任务已提交：{task_id}")

# 查询任务状态
response = requests.get(f"{API_BASE}/api/tasks/{task_id}")
task = response.json()
print(f"进度：{task['progress']['progress_percent']}%")

# 取消任务
response = requests.delete(f"{API_BASE}/api/tasks/{task_id}")
print(response.json())

# 列出缓存
response = requests.get(f"{API_BASE}/api/cache/list")
caches = response.json()["caches"]
for cache in caches:
    print(f"URL: {cache['url']}, 大小：{cache['total_size_mb']} MB")

# 删除缓存
response = requests.delete(f"{API_BASE}/api/cache/{cache_id}")
print(response.json())

# 获取服务器配置
response = requests.get(f"{API_BASE}/api/config")
config = response.json()
print(f"最大并发数：{config['max_threads']}")
```

---

## 注意事项

1. **下载接口**：
   - `/api/download` 是异步接口，提交任务后立即返回 `task_id`
   - 使用 `--trace` 选项可以在提交任务后通过短轮询（0.5 秒间隔）跟踪进度
   - **task_id 与 cache_id 的关系**：`task_id` 是 URL 的 MD5 哈希值（前 16 位字符），与 `cache_id` 完全一致
     - 同一 URL 的下载任务始终共享同一个 task_id
     - 可以使用 task_id 直接访问 `/api/cache/<task_id>` 获取缓存信息

2. **缓存 ID 生成规则**：缓存 ID 是 m3u8 URL 的 MD5 哈希值的前 16 位字符（与 task_id 一致）。

3. **线程数配置**：
   - 如果请求中未指定 `threads`，使用服务器启动时的 `--max-threads` 配置
   - 如果请求中指定了 `threads`，使用请求中的值，但不会超过 `--max-threads` 的上限

4. **缓存清理**：
   - 下载完成后，默认会清理分片文件，保留元数据和 m3u8 文件
   - 设置 `keep_cache: true` 可以保留所有文件
   - 删除缓存时，如果缓存正在被任务引用，会拒绝删除（返回 409 Conflict）

5. **日志文件**：
   - 默认日志目录：`logs/`
   - 默认日志文件：`logs/m3u8-downloader.log`
   - 日志文件会自动轮转，最大 10MB，保留 5 个文件

6. **任务状态**：
   - `pending`: 等待执行
   - `parsing`: 解析 m3u8 中
   - `downloading`: 下载分片中
   - `merging`: 合并分片中
   - `completed`: 已完成
   - `failed`: 失败
   - `cancelled`: 已取消

7. **任务删除**：
   - 删除正在运行的任务时，会先取消任务再删除
   - 删除已结束的任务（completed/failed/cancelled）时，直接删除

8. **缓存保护机制**：
   - `/api/cache/clear` 会跳过正在被任务引用的缓存
   - `/api/cache/<id>` DELETE 会拒绝删除正在被任务引用的缓存
