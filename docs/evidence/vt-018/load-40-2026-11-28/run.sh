#!/bin/bash
# 40 client, --search 4, thư mục lưu trống mỗi lượt (--storage temp), 6 lượt liên tiếp trên main sau #83 và #84.
# DB=<URL Postgres trống> bash run.sh
set -u
: "${DB:?đặt DB=postgresql+psycopg://...}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
for i in 1 2 3 4 5 6; do
  echo "r$i $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  uv run python scripts/load_vt018.py --db "$DB" --clients 40 --threshold 1.5 --search 4 --out "$REL/r$i" > /dev/null 2>&1
  echo "r$i exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 15
done
echo DONE >> "$OUT/run-log.txt"
