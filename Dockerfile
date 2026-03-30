# m3u8-downloader 后端服务 Docker 镜像（两阶段构建优化版）

FROM alpine:3.23 AS ffmpeg-builder

RUN apk update

RUN apk add --no-cache build-base
RUN apk add --no-cache pkgconf zlib-dev nasm wget

RUN apk add --no-cache x264-dev x265-dev svt-av1-dev
# RUN apk add --no-cache libva-dev libdrm-dev

ENV FFMPEG_VERSION=8.1 \
    PREFIX=/ffmpeg

RUN wget --no-check-certificate https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.gz \
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
    # --disable-postproc \
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
    --enable-gpl \
    --enable-nonfree \
    \
    --enable-muxer=mp4 \
    \
    --enable-encoder=aac \
    \
    # 硬件加速库
    # --enable-libdrm \
    \
    # 软件编码器
    # --enable-libx264 \
    # --enable-encoder=libx264 \
    \
    # --enable-libx265 \
    # --enable-encoder=libx265 \
    \
    # --enable-libsvtav1 \
    # --enable-encoder=libsvtav1 \
    \
    # Nvdia 硬件编码器
    # --enable-ffnvcodec \
    # --enable-nvenc \
    # --enable-encoder=h264_nvenc \
    # --enable-encoder=hevc_nvenc \
    # --enable-encoder=av1_nvenc \
    \
    # Intel 硬件编码器
    # --enable-qsv \
    # --enable-encoder=h264_qsv \
    # --enable-encoder=hevc_qsv \
    # --enable-encoder=av1_qsv \
    \
    # AMD/Intel 硬件编码器
    # --enable-vaapi \
    # --enable-encoder=h264_vaapi \
    # --enable-encoder=hevc_vaapi \
    # --enable-encoder=av1_vaapi \
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

# RUN cat /etc/alpine-release && sleep 10s
# RUN /ffmpeg/bin/ffmpeg

# ==============================================================================
# 阶段二：Python 运行时 + 编译好的 ffmpeg
# ==============================================================================
FROM python:3.12-alpine

RUN apk update \
    && apk add --no-cache \
    # x264-libs x265-libs libSvtAv1Enc \
    && mkdir -p /app /data/logs /output /data/temp_segments \
    && pip install --no-cache-dir quart quart-cors aiohttp m3u8 bitarray pydantic

COPY --from=ffmpeg-builder /ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg
COPY backend/ /app/
COPY docker-entrypoint.sh /docker-entrypoint.sh

# RUN cat /etc/alpine-release && sleep 10s

# RUN ffmpeg -v

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
