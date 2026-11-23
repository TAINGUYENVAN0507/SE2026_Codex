#!/bin/bash
# 247 client, 2 process API, xen kẽ không tìm kiếm (--search 0) và có tìm kiếm (--search 4) theo thứ tự
# ABBA ABBA, 8 lượt, trên main sau #69 và #70. Thư mục lưu trống mỗi lượt (--storage temp, mặc định từ 11-23).
# Mục đích: tách phần chậm do tìm kiếm khỏi dao động của máy (11-19 không tách được). DB=<URL Postgres trống> bash run.sh
set -u
: "${DB:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
i=0
for search in 0 4 4 0 0 4 4 0; do
  i=$((i + 1))
  v=s$search-$i
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
    --api-workers 2 --client-procs 4 --search "$search" --out "$REL/$v" > "$OUT/$v.stdout" 2>&1
  echo "$v exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 30
done
echo DONE >> "$OUT/run-log.txt"
