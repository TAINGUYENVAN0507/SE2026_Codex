#!/bin/bash
# 247 client, 1 và 4 process API xen kẽ (1 4 4 1 1 4), có tìm kiếm (--search 4), thư mục lưu trống mỗi lượt
# (--storage temp), trên main sau #71 và #72. Bổ sung cho 2 process ngày 11-23. DB=<URL Postgres trống> bash run.sh
set -u
: "${DB:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
i=0
for workers in 1 4 4 1 1 4; do
  i=$((i + 1))
  v=p$workers-$i
  inflight=()
  # Ngân sách kết nối: workers × API_MAX_INFLIGHT + dự phòng ≤ max_connections 100.
  [ "$workers" = 4 ] && inflight=(env API_MAX_INFLIGHT=20)
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  "${inflight[@]}" uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
    --api-workers "$workers" --client-procs 4 --search 4 --out "$REL/$v" > "$OUT/$v.stdout" 2>&1
  echo "$v exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 30
done
echo DONE >> "$OUT/run-log.txt"
