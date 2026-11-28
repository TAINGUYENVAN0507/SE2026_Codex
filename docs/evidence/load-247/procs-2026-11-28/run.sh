#!/bin/bash
# 247 client trên main sau #83, #84; --search 4, thư mục lưu trống; 2 và 4 process API xen kẽ ABBA ABBA, 8 lượt:
#   p2 = 2 process, API_MAX_INFLIGHT 40 (mặc định): 2 × 40 + 20 = 100 kết nối
#   p4 = 4 process, API_MAX_INFLIGHT 20:            4 × 20 + 20 = 100 kết nối = max_connections
# Hai cấu hình cùng code, cùng ngân sách kết nối. DB=<URL Postgres trống> bash run.sh
set -u
: "${DB:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
i=0
for p in 2 4 4 2 2 4 4 2; do
  i=$((i + 1))
  v=p$p-$i
  inflight=40; [ "$p" = 4 ] && inflight=20
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  API_MAX_INFLIGHT=$inflight uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
    --api-workers "$p" --client-procs 4 --search 4 --out "$REL/$v" > /dev/null 2>&1
  echo "$v exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 30
done
echo DONE >> "$OUT/run-log.txt"
