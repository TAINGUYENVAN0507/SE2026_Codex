#!/bin/sh
# AD-018: error log nginx không có log_format; lọc query nhưng giữ nội dung chẩn đoán.
set -eu
pipe=/tmp/nginx-request-errors.fifo
if [ ! -p "$pipe" ]; then
    mkfifo "$pipe"
fi
awk '{ gsub(/\?[^[:space:]"<>]*/, "?[redacted]"); print; fflush() }' < "$pipe" >&2 &
