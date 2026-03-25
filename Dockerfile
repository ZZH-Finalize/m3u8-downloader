# m3u8-downloader 后端服务 Docker 镜像（两阶段构建优化版）

# ==============================================================================
# 阶段一：编译最小化 ffmpeg（仅 HLS 合并，-c copy 模式）
# ==============================================================================
FROM alpine:3.19 AS ffmpeg-builder

ENV FFMPEG_VERSION=6.1.4 \
    PREFIX=/ffmpeg

RUN echo "http://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories \
    && apk update\
    && apk add --no-cache \
    build-base \
    pkgconf \
    zlib-dev \
    nasm \
    wget \
    x264-dev x265-dev aom-dev \
    && wget --no-check-certificate https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.gz \
    && tar -xzf ffmpeg-${FFMPEG_VERSION}.tar.gz

RUN cd ffmpeg-${FFMPEG_VERSION} \
    && ./configure \
    --prefix=${PREFIX} \
    --disable-everything \
    --disable-shared \
    --disable-doc \
    --disable-ffplay \
    --disable-ffprobe \
    --disable-avdevice \
    --disable-swresample \
    --disable-postproc \
    --disable-filters \
    \
    --enable-static \
    --enable-small \
    # --optimize-for-size \
    \
    --enable-decoders \
    --enable-parsers \
    --enable-demuxers \
    \
    --enable-muxer=mp4 \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libaom \
    --enable-gpl \
    --enable-encoder=aac \
    \
    --enable-bsf=aac_adtstoasc \
    --enable-bsf=h264_mp4toannexb \
    --enable-bsf=hevc_mp4toannexb \
    --enable-protocol=file \
    --extra-libs="-lpthread -lm -lz" \
    && make -j$(nproc) \
    && make install \
    && strip ${PREFIX}/bin/ffmpeg \
    && rm -rf /ffmpeg-${FFMPEG_VERSION}* /build

# ==============================================================================
# 阶段二：Python 运行时 + 编译好的 ffmpeg
# ==============================================================================
FROM python:3.12-alpine

RUN apk add --no-cache libgcc libstdc++ zlib x264 x265-libs aom \
    && mkdir -p /app /data/logs /output /data/temp_segments \
    && pip install --no-cache-dir quart quart-cors aiohttp m3u8 bitarray pydantic

COPY --from=ffmpeg-builder /ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg
COPY backend/ /app/
COPY docker-entrypoint.sh /docker-entrypoint.sh

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
    CACHE_DIR=/data/task_cache \
    OUTPUT_DIR=/output

WORKDIR /

EXPOSE 6900

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6900/health')" || exit 1

ENTRYPOINT ["sh", "/docker-entrypoint.sh"]
CMD ["python", "/app/server.py"]
