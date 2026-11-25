#!/bin/bash
# 247 client, 2 process API, --search 4, thư mục lưu trống; xen kẽ app trước bản sửa N+1 (b35e06f, trước #75)
# và sau (main sau #74, #75) theo ABBA ABBA, 8 lượt. Harness giống nhau ở hai bản.
# OLD=<worktree tại b35e06f> DB=<URL Postgres trống> bash run.sh
# Lượt "before" chạy trong worktree OLD với --out tương đối trong worktree rồi chép về đây, để env.json
# không ghi đường dẫn của máy đo.
set -u
: "${DB:?}" "${OLD:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
NEW="$OUT/../../../../backend"
REL=$(cd "$NEW" && realpath --relative-to=. "$OUT")
i=0
for app in before after after before before after after before; do
  i=$((i + 1))
  v=$app-$i
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  if [ "$app" = before ]; then
    (cd "$OLD/backend" && rm -rf "run-$v" && uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
      --api-workers 2 --client-procs 4 --search 4 --out "run-$v" > "$OUT/$v.stdout" 2>&1); rc=$?
    cp -r "$OLD/backend/run-$v" "$OUT/$v"
  else
    (cd "$NEW" && uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
      --api-workers 2 --client-procs 4 --search 4 --out "$REL/$v" > "$OUT/$v.stdout" 2>&1); rc=$?
  fi
  echo "$v exit=$rc $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 30
done
echo DONE >> "$OUT/run-log.txt"
