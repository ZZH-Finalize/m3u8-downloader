#!/bin/sh

CMD_ARGS=""

if [ -n "$SERVER_HOST" ]; then
    CMD_ARGS="$CMD_ARGS --host $SERVER_HOST"
fi

if [ -n "$SERVER_PORT" ]; then
    CMD_ARGS="$CMD_ARGS --port $SERVER_PORT"
fi

if [ -n "$MAX_THREADS" ]; then
    CMD_ARGS="$CMD_ARGS --max-threads $MAX_THREADS"
fi

if [ -n "$LOG_LEVEL" ]; then
    CMD_ARGS="$CMD_ARGS --log-level $LOG_LEVEL"
fi

if [ -n "$LOG_DIR" ]; then
    CMD_ARGS="$CMD_ARGS --log-dir $LOG_DIR"
fi

if [ "$DEBUG" = "true" ]; then
    CMD_ARGS="$CMD_ARGS --debug"
fi

if [ -n "$CACHE_DIR" ]; then
    CMD_ARGS="$CMD_ARGS --cache-dir $CACHE_DIR"
fi

if [ -n "$OUTPUT_DIR" ]; then
    CMD_ARGS="$CMD_ARGS --output-dir $OUTPUT_DIR"
fi

exec $@ $CMD_ARGS
