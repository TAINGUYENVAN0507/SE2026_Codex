#!/bin/bash
# 247 client, 1, 2 và 4 process API, 3 vòng, thứ tự xoay vòng (hình vuông Latin) như 11-16.
# Chạy trên main sau #61 và #64. Harness ghi thêm số dòng log của API và dòng có query string (api_log).
# DB=<URL Postgres trống> bash run.sh
set -u
: "${DB:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
ORDERS=("1 2 4" "2 4 1" "4 1 2")
for i in 1 2 3; do
  for workers in ${ORDERS[$((i - 1))]}; do
    v=p$workers-$i
    inflight=()
    # Ngân sách kết nối: workers × API_MAX_INFLIGHT + dự phòng ≤ max_connections 100.
    [ "$workers" = 4 ] && inflight=(env API_MAX_INFLIGHT=20)
    echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    "${inflight[@]}" uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
      --api-workers "$workers" --client-procs 4 --out "$REL/$v" > "$OUT/$v.stdout" 2>&1
    echo "$v exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    sleep 15
  done
done
echo DONE >> "$OUT/run-log.txt"
