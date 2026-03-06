# m3u8-downloader 后端服务 Docker 镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 默认环境变量（可在 docker-compose.yml 或 docker run 时覆盖）
ENV SERVER_HOST=0.0.0.0 \
    SERVER_PORT=5000 \
    DEFAULT_THREADS=8 \
    LOG_LEVEL=INFO \
    LOG_DIR=logs \
    DEBUG=false \
    FFMPEG_PATH=ffmpeg

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/
COPY start_server_async.py .

# 创建下载目录和日志目录
RUN mkdir -p /app/downloads /app/logs

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# 启动脚本，支持环境变量配置
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "start_server_async.py"]
