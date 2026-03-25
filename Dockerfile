# m3u8-downloader 后端服务 Docker 镜像（两阶段构建优化版）

# ==============================================================================
# 阶段一：编译最小化 ffmpeg（仅 HLS 合并，-c copy 模式）
# ==============================================================================
FROM alpine:3.19 AS ffmpeg-builder

ENV FFMPEG_VERSION=6.1 \
    PREFIX=/ffmpeg

RUN apk add --no-cache --virtual .build-deps \
    build-base \
    pkgconf \
    zlib-dev \
    nasm \
    wget \
    && wget --no-check-certificate https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.gz \
    && tar -xzf ffmpeg-${FFMPEG_VERSION}.tar.gz \
    && cd ffmpeg-${FFMPEG_VERSION} \
    && ./configure \
    --prefix=${PREFIX} \
    --enable-static \
    --disable-shared \
    --disable-doc \
    --disable-ffplay \
    --disable-ffprobe \
    --disable-avdevice \
    --disable-swresample \
    --disable-postproc \
    --disable-filters \
    --disable-encoders \
    --disable-decoders \
    --disable-parsers \
    --enable-demuxer=mpegts \
    --enable-demuxer=hls \
    --enable-demuxer=aac \
    --enable-demuxer=ac3 \
    --enable-demuxer=eac3 \
    --enable-demuxer=flv \
    --enable-demuxer=matroska \
    --enable-demuxer=mov \
    --enable-demuxer=mpegps \
    --enable-demuxer=mpegtsraw \
    --enable-demuxer=webm \
    --enable-demuxer=ogg \
    --enable-demuxer=wav \
    --enable-muxer=mpegts \
    --enable-muxer=matroska \
    --enable-muxer=mp4 \
    --enable-muxer=ogg \
    --enable-parser=aac \
    --enable-parser=h264 \
    --enable-parser=hevc \
    --enable-parser=vp9 \
    --enable-bsf=aac_adtstoasc \
    --enable-bsf=h264_mp4toannexb \
    --enable-bsf=hevc_mp4toannexb \
    --enable-protocol=file \
    --enable-protocol=http \
    --enable-protocol=https \
    --enable-protocol=tcp \
    --enable-protocol=udp \
    --extra-libs="-lpthread -lm -lz" \
    && make -j$(nproc) \
    && make install \
    && strip ${PREFIX}/bin/ffmpeg \
    && apk del .build-deps \
    && rm -rf /ffmpeg-${FFMPEG_VERSION}* /build

# ==============================================================================
# 阶段二：Python 运行时 + 编译好的 ffmpeg
# ==============================================================================
FROM python:3.12-alpine

RUN apk add --no-cache \
    libgcc \
    libstdc++ \
    zlib

COPY --from=ffmpeg-builder /ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg

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

RUN mkdir -p /app /data/logs /output /data/temp_segments

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 6900

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:6900/health')" || exit 1

WORKDIR /

ENTRYPOINT ["sh", "/docker-entrypoint.sh"]
CMD ["python", "/app/server.py"]
