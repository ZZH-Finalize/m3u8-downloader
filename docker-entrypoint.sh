#!/bin/sh
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

# 下载并发数上限
if [ -n "$MAX_THREADS" ]; then
    ARGS="$ARGS --max-threads $MAX_THREADS"
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

# 缓存目录
if [ -n "$CACHE_DIR" ]; then
    ARGS="$ARGS --cache-dir $CACHE_DIR"
fi

# 输出目录
if [ -n "$OUTPUT_DIR" ]; then
    ARGS="$ARGS --output-dir $OUTPUT_DIR"
fi

# 执行命令（使用引号确保参数正确传递）
exec "$@" $ARGS
