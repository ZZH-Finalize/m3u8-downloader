# m3u8-downloader 后端服务 Docker 镜像（优化版）
FROM python:3.12-alpine

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=6900 \
    MAX_THREADS=32 \
    LOG_LEVEL=INFO \
    LOG_DIR=/data/logs \
    DEBUG=false \
    TEMP_DIR=/data/temp_segments \
    OUTPUT_DIR=/output

# 安装 ffmpeg（Alpine 的 apk 包管理更精简）
RUN apk add --no-cache ffmpeg

# 创建必要目录
RUN mkdir -p /app /data/logs /output /data/temp_segments

# 设置工作目录
WORKDIR /app

# 复制并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ ./
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 暴露端口
EXPOSE 6900

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6900/health')" || exit 1

# 切换到根目录工作
WORKDIR /

ENTRYPOINT ["sh", "/docker-entrypoint.sh"]
CMD ["python", "/app/server.py"]
