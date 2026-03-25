# m3u8 下载器 - API 文档

本文档详细说明了 m3u8 下载器后端服务提供的所有 RESTful API 端点。

## 基本信息

- **基础 URL**: `http://<host>:<port>`
- **默认地址**: `http://127.0.0.1:6900`
- **数据格式**: JSON
- **字符编码**: UTF-8
- **框架**: Quart (异步) + Hypercorn

---

## 启动参数

启动后端服务时可配置以下参数：

```bash
python backend/server.py [选项]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `127.0.0.1` | 监听地址 IP |
| `--port` | `6900` | 监听端口 |
| `--max-threads` | `32` | 下载并发数上限。如果 API 请求传入的 `threads` 值大于此值，将使用此值。 |
| `--log-level` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `--log-dir` | `data/logs` | 日志目录 |
| `--debug` | - | 启用调试模式（等同于 `--log-level DEBUG`） |
| `--temp-dir` | `data/task_cache` | 临时分片及缓存目录 |
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
| `/api/tasks/<id>/pause` | POST | 暂停任务 |
| `/api/tasks/<id>/resume` | POST | 恢复任务 |
| `/api/tasks/<id>` | DELETE | 删除任务 |

### 缓存管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cache/list` | GET | 列出所有缓存 |
| `/api/cache/<id>` | GET | 获取缓存详情 |
| `/api/cache/<id>` | DELETE | 删除指定缓存（如果缓存被任务引用则拒绝删除） |
| `/api/cache/clear` | POST | 清空所有缓存（跳过正在被任务引用的缓存） |

### 系统 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/config` | GET | 获取服务器配置 |

---

## API 端点详解

### 1. 健康检查

检查服务是否正常运行。

**请求**
```http
GET /health
```

**响应**
```json
{
    "version": "0.1"
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
    "version": "0.1",
    "host": "127.0.0.1",
    "port": 6900,
    "max_threads": 32,
    "log_level": "INFO",
    "log_dir": "data/logs",
    "debug": false,
    "cache_dir": "data/task_cache",
    "output_dir": "output"
}
```

**字段说明**
| 字段 | 类型 | 说明 |
|------|------|------|
| `version` | string | 服务版本 |
| `host` | string | 监听地址 |
| `port` | int | 监听端口 |
| `max_threads` | int | 下载并发数上限 |
| `log_level` | string | 当前日志级别 |
| `log_dir` | string | 日志目录路径 |
| `debug` | boolean | 是否启用调试模式 |
| `cache_dir` | string | 临时缓存目录 |
| `output_dir` | string | 输出目录 |

**状态码**
- `200 OK`: 成功

---

### 3. 提交异步下载任务

提交下载任务，立即返回 `task_id`，后台异步执行。

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
    "output_name": "video.mp4",
    "output_encoding": "copy",
    "max_rounds": 5,
    "max_retry": 5,
    "keep_cache": false,
    "queued": false
}
```

**请求参数**
| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | 是 | - | m3u8 文件的 URL |
| `threads` | int | 否 | `max-threads` | 下载并发数（如果大于 `max-threads`，则使用 `max-threads`） |
| `output_name` | string | 否 | `output.mp4` | 输出文件名 |
| `output_encoding` | string | 否 | `copy` | 视频编码格式（可选值：`copy`/`x264`/`x265`/`AV1`） |
| `max_rounds` | int | 否 | `5` | 最大下载轮次（重试次数） |
| `max_retry` | int | 否 | `5` | 每个分片的最大重试次数 |
| `keep_cache` | boolean | 否 | `false` | 是否保留缓存文件 |
| `queued` | boolean | 否 | `false` | 是否加入队列（排队等待执行） |

**成功响应**
```json
{
    "task_id": "74a993fffd15ddbe"
}
```

**说明**
- 该接口是异步接口，提交任务后立即返回
- 使用返回的 `task_id` 可通过 `/api/tasks/<task_id>` 查询进度
- 下载过程包括：解析 m3u8、下载分片、合并为 MP4、清理分片
- **task_id 生成规则**: `task_id` 是 URL 的 MD5 哈希值（前 16 位字符）
  - 同一 URL 多次提交下载请求时，会复用同一个 `task_id`
  - 如果任务正在运行中（非 `COMPLETED`/`FAILED` 状态），返回空响应（不重复创建）
  - 如果任务已完成或失败，会重新执行任务

**状态码**
- `200 OK`: 请求成功
- `400 Bad Request`: 参数错误（如 url 为空）

---

### 4. 列出所有任务

获取所有任务的列表及下载进度。

**请求**
```http
GET /api/tasks
```

**响应**
```json
{
    "tasks": [
        {
            "url": "https://example.com/video.m3u8",
            "task_id": "74a993fffd15ddbe",
            "state": "downloading",
            "segments_downloaded": 45,
            "total_segments": 100,
            "output_name": "video.mp4"
        }
    ],
    "total_count": 1
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `tasks` | array | 任务列表 |
| `tasks[].url` | string | 原始 m3u8 URL |
| `tasks[].task_id` | string | 任务 ID |
| `tasks[].state` | string | 任务状态 (`pending`/`parsing`/`downloading`/`merging`/`paused`/`completed`/`failed`) |
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
    "url": "https://example.com/video.m3u8",
    "task_id": "74a993fffd15ddbe",
    "state": "downloading",
    "segments_downloaded": 45,
    "total_segments": 100,
    "output_name": "video.mp4"
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `url` | string | 原始 m3u8 URL |
| `task_id` | string | 任务 ID |
| `state` | string | 任务状态 (`pending`/`parsing`/`downloading`/`merging`/`paused`/`completed`/`failed`) |
| `segments_downloaded` | int | 已下载分片数 |
| `total_segments` | int | 总分片数 |
| `output_name` | string | 输出文件名 |

**状态码**
- `200 OK`: 成功
- `404 Not Found`: 任务不存在

---

### 6. 暂停任务

暂停正在执行的任务。

**请求**
```http
POST /api/tasks/<task_id>/pause
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |

**成功响应**
```json
{}
```

**说明**
- 仅当任务状态为 `PENDING`、`PARSING` 或 `DOWNLOADING` 时可暂停
- 暂停后任务状态变为 `PAUSED`
- 暂停的任务可通过 `/api/tasks/<task_id>/resume` 恢复

**状态码**
- `200 OK`: 成功
- `404 Not Found`: 任务不存在

---

### 7. 恢复任务

恢复已暂停的任务。

**请求**
```http
POST /api/tasks/<task_id>/resume
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |

**成功响应**
```json
{}
```

**说明**
- 仅当任务状态为 `PAUSED` 时可恢复
- 恢复后任务状态恢复到暂停前的状态（`PENDING`/`PARSING`/`DOWNLOADING`）

**状态码**
- `200 OK`: 成功
- `404 Not Found`: 任务不存在

---

### 8. 删除任务

删除任务。

**请求**
```http
DELETE /api/tasks/<task_id>
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |

**成功响应**
```json
{}
```

**说明**
- 如果任务正在运行（worker 不为 None），会先取消 worker 再删除
- 如果任务已结束，直接删除

**状态码**
- `200 OK`: 成功
- `404 Not Found`: 任务不存在

---

### 9. 列出所有缓存

获取所有缓存的视频信息。

**请求**
```http
GET /api/cache/list
```

**响应**
```json
{
    "caches": [
        {
            "id": "74a993fffd15ddbe",
            "url": "https://example.com/video.m3u8",
            "created_at": "2024-01-01T12:00:00.000000",
            "segments_num": 100
        }
    ],
    "total_count": 1
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `caches` | array | 缓存列表 |
| `caches[].id` | string | 缓存 ID（URL 的 MD5 哈希前 16 位） |
| `caches[].url` | string | 原始 m3u8 URL |
| `caches[].created_at` | string | 创建时间（ISO 8601） |
| `caches[].segments_num` | int | 分片总数 |
| `total_count` | int | 缓存总数 |

**状态码**
- `200 OK`: 成功

---

### 10. 获取缓存详情

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
    "id": "74a993fffd15ddbe",
    "url": "https://example.com/video.m3u8",
    "base_url": "https://example.com/video/",
    "state": "completed",
    "created_at": "2024-01-01T12:00:00.000000",
    "downloaded_mask": "ffffffffffffffff",
    "segments_num": 100,
    "segments": [
        "https://example.com/video/segment0.ts",
        "https://example.com/video/segment1.ts"
    ]
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 缓存 ID |
| `url` | string | 原始 m3u8 URL |
| `base_url` | string | 基准 URL |
| `state` | string | 任务状态 |
| `created_at` | string | 创建时间（ISO 8601） |
| `downloaded_mask` | string | 下载完成掩码（十六进制字符串，每位代表一个分片的下载状态） |
| `segments_num` | int | 分片总数 |
| `segments` | array | 分片 URL 列表 |

**状态码**
- `200 OK`: 成功
- `404 Not Found`: 缓存不存在

---

### 11. 删除指定缓存

删除单个缓存及其所有文件。

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
{}
```

**失败响应**
```json
{
    "msg": "74a993fffd15ddbe 被任务占用，拒绝删除"
}
```

**状态码**
- `200 OK`: 删除成功
- `403 Forbidden`: 缓存被任务占用，拒绝删除
- `404 Not Found`: 缓存不存在
- `500 Internal Server Error`: 删除失败（文件系统错误等）

---

### 12. 清空所有缓存

删除所有缓存，但会跳过正在被任务列表中的任务引用的缓存。

**请求**
```http
POST /api/cache/clear
```

**响应**
```json
{}
```

**说明**
- 会遍历 `cache_dir` 目录下的所有子目录
- 如果缓存 ID 存在于当前任务列表中，则跳过该缓存
- 其他缓存会被全部删除（删除失败的缓存会记录警告日志，但继续处理下一个）

**状态码**
- `200 OK`: 成功

---

## 错误响应格式

所有 API 错误都使用统一的响应格式：

```json
{
    "msg": "错误描述信息"
}
```

### 常见状态码

| HTTP 状态码 | 说明 |
|-------------|------|
| `200 OK` | 请求成功 |
| `400 Bad Request` | 请求参数错误或缺少必要参数 |
| `403 Forbidden` | 拒绝访问（如删除被任务占用的缓存） |
| `404 Not Found` | 资源不存在（任务或缓存不存在） |
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
    "output_name": "my_video.mp4"
  }'
```

#### 3. 列出所有任务
```bash
curl http://127.0.0.1:6900/api/tasks
```

#### 4. 查询任务状态
```bash
curl http://127.0.0.1:6900/api/tasks/74a993fffd15ddbe
```

#### 5. 暂停任务
```bash
curl -X POST http://127.0.0.1:6900/api/tasks/74a993fffd15ddbe/pause
```

#### 6. 恢复任务
```bash
curl -X POST http://127.0.0.1:6900/api/tasks/74a993fffd15ddbe/resume
```

#### 7. 删除任务
```bash
curl -X DELETE http://127.0.0.1:6900/api/tasks/74a993fffd15ddbe
```

#### 8. 列出缓存
```bash
curl http://127.0.0.1:6900/api/cache/list
```

#### 9. 获取缓存详情
```bash
curl http://127.0.0.1:6900/api/cache/74a993fffd15ddbe
```

#### 10. 删除缓存
```bash
curl -X DELETE http://127.0.0.1:6900/api/cache/74a993fffd15ddbe
```

#### 11. 清空所有缓存
```bash
curl -X POST http://127.0.0.1:6900/api/cache/clear
```

#### 12. 获取服务器配置
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
    "output_name": "my_video.mp4",
    "output_encoding": "copy"
})
result = response.json()
task_id = result["task_id"]
print(f"任务已提交：{task_id}")

# 列出所有任务
response = requests.get(f"{API_BASE}/api/tasks")
tasks = response.json()
for t in tasks["tasks"]:
    print(f"任务 {t['task_id']}: {t['segments_downloaded']}/{t['total_segments']}")

# 查询任务状态
response = requests.get(f"{API_BASE}/api/tasks/{task_id}")
task = response.json()
print(f"已下载：{task['segments_downloaded']}/{task['total_segments']}")

# 暂停任务
requests.post(f"{API_BASE}/api/tasks/{task_id}/pause")

# 恢复任务
requests.post(f"{API_BASE}/api/tasks/{task_id}/resume")

# 删除任务
response = requests.delete(f"{API_BASE}/api/tasks/{task_id}")
print(response.json())

# 列出缓存
response = requests.get(f"{API_BASE}/api/cache/list")
caches = response.json()["caches"]
for cache in caches:
    print(f"URL: {cache['url']}, 分片数：{cache['segments_num']}, 状态：{cache['state']}")

# 获取服务器配置
response = requests.get(f"{API_BASE}/api/config")
config = response.json()
print(f"最大并发数：{config['max_threads']}")
```

---

## 注意事项

1. **下载接口**：
   - `/api/download` 是异步接口，提交任务后立即返回 `task_id`
   - **task_id 生成规则**: `task_id` 是 URL 的 MD5 哈希值（前 16 位字符），与 `cache_id` 完全一致
   - 同一 URL 的下载任务始终共享同一个 `task_id`
   - 如果任务正在运行（非 `COMPLETED`/`FAILED` 状态），不会重复创建任务

2. **任务状态**：
   - `pending`: 等待执行
   - `parsing`: 解析 m3u8 中
   - `downloading`: 下载分片中
   - `merging`: 合并分片中
   - `paused`: 已暂停
   - `completed`: 已完成
   - `failed`: 失败

3. **任务暂停/恢复**：
   - 仅当任务状态为 `pending`/`parsing`/`downloading` 时可暂停
   - 仅当任务状态为 `paused` 时可恢复
   - 暂停的任务会保持当前进度，恢复后从断点继续

4. **缓存管理**：
   - 下载完成后，默认会清理分片文件（`keep_cache: false`）
   - 设置 `keep_cache: true` 可以保留所有分片文件
   - `/api/cache/clear` 会跳过正在被任务引用的缓存

5. **队列模式**：
   - 设置 `queued: true` 可将任务加入队列
   - 队列任务会等待当前并发任务完成后才执行
   - 同一时间只有一个队列任务在执行

6. **多分辨率支持**：
   - 自动检测多分辨率 m3u8
   - 自动选择最高分辨率的流进行下载

7. **重试机制**：
   - `max_retry`: 每个分片的最大重试次数（默认 5）
   - `max_rounds`: 最大下载轮次（默认 5），每轮下载所有失败的分片

8. **日志文件**：
   - 默认日志目录：`data/logs/`
   - 日志级别可通过 `--log-level` 或 `--debug` 配置
