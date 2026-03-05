# m3u8 下载器 - API 文档

本文档详细说明了 m3u8 下载器后端服务提供的所有 RESTful API 端点。

## 基本信息

- **基础 URL**: `http://<host>:<port>`
- **默认地址**: `http://127.0.0.1:5000`
- **数据格式**: JSON
- **字符编码**: UTF-8

## 启动参数

启动后端服务时可配置以下参数：

```bash
python start_server.py [选项]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `127.0.0.1` | 监听地址 IP |
| `--port` | `5000` | 监听端口 |
| `--default-threads` | `8` | 默认下载线程数（前端未提供时采用） |
| `--log-level` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `--log-dir` | `logs` | 日志目录 |
| `--debug` | - | 启用调试模式（等同于 --log-level DEBUG） |

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
    "service": "m3u8-downloader-api"
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
    "default_threads": 8,
    "log_level": "INFO",
    "log_dir": "logs"
}
```

**字段说明**
| 字段 | 类型 | 说明 |
|------|------|------|
| `default_threads` | int | 默认下载线程数 |
| `log_level` | string | 当前日志级别 |
| `log_dir` | string | 日志目录路径 |

---

### 3. 下载视频

下载 m3u8 视频并自动合并为 MP4 文件。

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
| `threads` | int | 否 | `default_threads` | 下载线程数 |
| `output` | string | 否 | `"video.mp4"` | 输出文件名 |
| `max_rounds` | int | 否 | `5` | 最大下载轮次（重试次数） |
| `keep_cache` | boolean | 否 | `false` | 是否保留缓存文件 |
| `debug` | boolean | 否 | `false` | 是否启用调试日志 |

**成功响应**
```json
{
    "success": true,
    "output_path": "output/abc123/video.mp4",
    "segments_downloaded": 100,
    "total_segments": 100
}
```

**失败响应**
```json
{
    "success": false,
    "error": "错误描述信息"
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `output_path` | string | 输出文件路径（成功时） |
| `segments_downloaded` | int | 成功下载的分片数 |
| `total_segments` | int | 总分片数 |
| `error` | string | 错误信息（失败时） |

**状态码**
- `200 OK`: 请求成功
- `400 Bad Request`: 参数错误
- `500 Internal Server Error`: 服务器错误

**说明**
- 该接口是同步接口，会等待下载完成才返回
- 下载过程包括：解析 m3u8、下载分片、合并为 MP4、清理分片
- 如果 `threads` 未提供，使用服务器启动时配置的 `--default-threads` 值

---

### 4. 列出所有缓存

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

---

### 5. 获取缓存详情

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

### 6. 删除指定缓存

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
{
    "success": true,
    "message": "缓存已删除：74a993fffd15ddbe"
}
```

**失败响应**
```json
{
    "success": false,
    "error": "缓存不存在：74a993fffd15ddbe"
}
```

**状态码**
- `200 OK`: 删除成功
- `404 Not Found`: 缓存不存在
- `500 Internal Server Error`: 删除失败

---

### 7. 清空所有缓存

删除所有缓存。

**请求**
```http
POST /api/cache/clear
```

**响应**
```json
{
    "success": true,
    "deleted_count": 5,
    "message": "已删除 5 个缓存"
}
```

**响应字段**
| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `deleted_count` | int | 删除的缓存数量 |
| `message` | string | 结果消息 |

---

### 8. 更新缓存元数据

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
| `404 Not Found` | 资源不存在（如缓存不存在） |
| `500 Internal Server Error` | 服务器内部错误 |

---

## 使用示例

### 使用 curl 调用

#### 1. 健康检查
```bash
curl http://127.0.0.1:5000/health
```

#### 2. 下载视频
```bash
curl -X POST http://127.0.0.1:5000/api/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/video.m3u8",
    "threads": 8,
    "output": "my_video.mp4"
  }'
```

#### 3. 列出缓存
```bash
curl http://127.0.0.1:5000/api/cache/list
```

#### 4. 删除缓存
```bash
curl -X DELETE http://127.0.0.1:5000/api/cache/74a993fffd15ddbe
```

#### 5. 清空所有缓存
```bash
curl -X POST http://127.0.0.1:5000/api/cache/clear
```

#### 6. 更新缓存元数据
```bash
curl -X POST http://127.0.0.1:5000/api/cache/update \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.m3u8"}'
```

### 使用 Python 调用

```python
import requests

API_BASE = "http://127.0.0.1:5000"

# 下载视频
response = requests.post(f"{API_BASE}/api/download", json={
    "url": "https://example.com/video.m3u8",
    "threads": 8,
    "output": "my_video.mp4"
})
result = response.json()
print(result)

# 列出缓存
response = requests.get(f"{API_BASE}/api/cache/list")
caches = response.json()["caches"]
for cache in caches:
    print(f"URL: {cache['url']}, 大小：{cache['total_size_mb']} MB")

# 删除缓存
response = requests.delete(f"{API_BASE}/api/cache/{cache_id}")
```

---

## 注意事项

1. **下载接口是同步的**：`/api/download` 会等待整个下载过程完成才返回，对于大文件可能需要较长时间。

2. **缓存 ID 生成规则**：缓存 ID 是 m3u8 URL 的 MD5 哈希值的前 16 位字符。

3. **线程数配置**：
   - 如果请求中未指定 `threads`，使用服务器启动时的 `--default-threads` 配置
   - 如果请求中指定了 `threads`，使用请求中的值

4. **缓存清理**：
   - 下载完成后，默认会清理分片文件，保留元数据和 m3u8 文件
   - 设置 `keep_cache: true` 可以保留所有文件

5. **日志文件**：
   - 默认日志目录：`logs/`
   - 默认日志文件：`logs/m3u8-downloader.log`
   - 日志文件会自动轮转，最大 10MB，保留 5 个文件
