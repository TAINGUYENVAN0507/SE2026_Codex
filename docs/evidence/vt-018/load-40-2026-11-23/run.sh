#!/bin/bash
# 40 client, --search 4, 6 lượt xen kẽ thư mục lưu trống (--storage temp) và backend/appdata thật
# (--storage real, 22.950 thư mục audio cũ) theo thứ tự ABBAAB, trên main sau #69 và #70.
# DB=<URL Postgres trống> bash run.sh
set -u
: "${DB:?đặt DB=postgresql+psycopg://...}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
i=0
for storage in temp real real temp temp real; do
  i=$((i + 1))
  v=$storage-$i
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg) real_audio_dirs=$(ls appdata/audio 2>/dev/null | wc -l)" >> "$OUT/run-log.txt"
  uv run python scripts/load_vt018.py --db "$DB" --clients 40 --threshold 1.5 --search 4 --storage "$storage" --out "$REL/$v" > "$OUT/$v.stdout" 2>&1
  echo "$v exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 15
done
echo DONE >> "$OUT/run-log.txt"
