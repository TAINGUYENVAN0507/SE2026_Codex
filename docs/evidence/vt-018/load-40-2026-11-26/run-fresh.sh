#!/bin/bash
# Thêm sau 6 lượt đầu, vì r1 (lượt đầu tiên trên DB load40 vừa tạo) không đạt.
# Hai vòng: tạo lại DB trống rồi chạy "fresh", sau đó chạy "warm" trên cùng DB. Cấu hình như run.sh.
# PGBIN=<thư mục bin của Postgres 16> PGPORT=<cổng> bash run-fresh.sh
set -u
: "${PGBIN:?}" "${PGPORT:?}"
DB=postgresql+psycopg://postgres@127.0.0.1:$PGPORT/load40
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")
for k in 1 2; do
  "$PGBIN/dropdb" -h 127.0.0.1 -p "$PGPORT" -U postgres load40
  "$PGBIN/createdb" -h 127.0.0.1 -p "$PGPORT" -U postgres load40
  for v in fresh$k warm$k; do
    echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    uv run python scripts/load_vt018.py --db "$DB" --clients 40 --threshold 1.5 --search 4 --out "$REL/$v" > /dev/null 2>&1
    echo "$v exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    sleep 15
  done
done
echo DONE-FRESH >> "$OUT/run-log.txt"
