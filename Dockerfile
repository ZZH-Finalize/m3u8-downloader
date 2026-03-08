# m3u8-downloader 后端服务 Docker 镜像
FROM python:3.12-slim

# 设置应用目录
WORKDIR /app

# 设置环境变量（Python 优化 + 服务器配置 + PYTHONPATH）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=6900 \
    DEFAULT_THREADS=8 \
    LOG_LEVEL=INFO \
    LOG_DIR=/data/logs \
    DEBUG=false \
    TEMP_DIR=/data/temp_segments \
    OUTPUT_DIR=/output

VOLUME ["/output", "/data"]

# 安装 ffmpeg 和 Python 依赖（合并指令减少层数）
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip && \
    mkdir -p /data/logs "$OUTPUT_DIR" "$TEMP_DIR"

# 复制并安装依赖（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码（backend 内容直接放到 /app）
COPY backend/ ./
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 暴露端口
EXPOSE 6900

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6900/health')" || exit 1

# 切换工作目录到根目录
WORKDIR /

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "/app/server.py"]
