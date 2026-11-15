#!/bin/bash
# A/B app ở 247 client, 4 process API, chung CPU: app 11-11 (1f9d1ca) và main hôm nay, xen kẽ 3 cặp.
# DB=<URL Postgres trống> OLD=<git worktree tại 1f9d1ca> bash run.sh
# Worktree dùng harness của hôm nay (chép vào, không commit) và symlink appdata về thư mục lưu
# của repo chính, để hai bản chỉ khác nhau ở backend/app.
set -u
: "${DB:?}" "${OLD:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
MAIN=$(cd "$OUT/../../../../../backend" && pwd)
for i in 1 2 3; do
  for v in old-1f9d1ca main-115c905; do
    if [ "$v" = old-1f9d1ca ]; then dir=$OLD/backend; else dir=$MAIN; fi
    cd "$dir"
    echo "$v-$i $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg) head=$(git rev-parse --short HEAD)" >> "$OUT/run-log.txt"
    API_MAX_INFLIGHT=20 uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
      --api-workers 4 --client-procs 4 --out "$(realpath --relative-to=. "$OUT")/$v-$i" > "$OUT/$v-$i.stdout" 2>&1
    echo "$v-$i exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    sleep 15
  done
done
echo DONE >> "$OUT/run-log.txt"
