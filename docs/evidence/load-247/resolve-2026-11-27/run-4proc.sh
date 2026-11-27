#!/bin/bash
# Thêm sau 8 lượt ABBA, vì cả 8 lượt 2 process đều không đạt khi máy đang bận (trình duyệt, VS Code).
# 2 lượt main với 4 process API, cấu hình còn lại như run.sh. Ngân sách kết nối như 11-24:
# 4 process × API_MAX_INFLIGHT 20 + 20 dự phòng = 100 = max_connections của Postgres.
# DB=<URL Postgres> bash run-4proc.sh
set -u
: "${DB:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")
for v in main4p-1 main4p-2; do
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  API_MAX_INFLIGHT=20 uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 --api-workers 4 \
    --client-procs 4 --search 4 --out "$REL/$v" > /dev/null 2>&1
  echo "$v exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 30
done
echo DONE-4PROC >> "$OUT/run-log.txt"
