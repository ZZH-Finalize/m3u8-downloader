#!/bin/bash
set -e

# 构建启动参数
ARGS=""

# 主机地址
if [ -n "$SERVER_HOST" ]; then
    ARGS="$ARGS --host $SERVER_HOST"
fi

# 端口
if [ -n "$SERVER_PORT" ]; then
    ARGS="$ARGS --port $SERVER_PORT"
fi

# 默认下载并发数
if [ -n "$DEFAULT_THREADS" ]; then
    ARGS="$ARGS --default-threads $DEFAULT_THREADS"
fi

# 日志级别
if [ -n "$LOG_LEVEL" ]; then
    ARGS="$ARGS --log-level $LOG_LEVEL"
fi

# 日志目录
if [ -n "$LOG_DIR" ]; then
    ARGS="$ARGS --log-dir $LOG_DIR"
fi

# 调试模式
if [ "$DEBUG" = "true" ]; then
    ARGS="$ARGS --debug"
fi

# FFmpeg 路径
if [ -n "$FFMPEG_PATH" ]; then
    ARGS="$ARGS --ffmpeg-path $FFMPEG_PATH"
fi

# 执行命令
exec $@ $ARGS
