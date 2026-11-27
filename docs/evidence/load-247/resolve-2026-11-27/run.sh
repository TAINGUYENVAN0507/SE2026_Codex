#!/bin/bash
# 247 client, 2 process API, --search 4, thư mục lưu trống; xen kẽ ABBA ABBA, 8 lượt:
#   pre81 = main hôm qua db8072b (sau #77, #78; trước #80, #81)
#   main  = main sau #80, #81 (4259a4f; working tree có thêm commit test của C, backend/app như 4259a4f)
# #81 thêm resolve_audio_file (resolve + is_relative_to + is_file) cho mỗi mục của GET /meetings.
# Harness (backend/scripts) và uv.lock giống hệt ở hai bản.
# WOLD=<worktree db8072b> DB=<URL Postgres trống> bash run.sh
# Lượt của worktree chạy với --out tương đối trong worktree rồi chép về đây, để env.json không ghi
# đường dẫn của máy đo. stdout không giữ vì trùng với summary.md của mỗi lượt.
set -u
: "${DB:?}" "${WOLD:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
NEW="$OUT/../../../../backend"
REL=$(cd "$NEW" && realpath --relative-to=. "$OUT")
i=0
for app in pre81 main main pre81 pre81 main main pre81; do
  i=$((i + 1))
  v=$app-$i
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  ARGS=(--db "$DB" --clients 247 --threshold 2.0 --api-workers 2 --client-procs 4 --search 4)
  if [ "$app" = pre81 ]; then
    (cd "$WOLD/backend" && rm -rf "run-$v" && uv run python scripts/load_vt018.py "${ARGS[@]}" \
      --out "run-$v" > /dev/null 2>&1); rc=$?
    cp -r "$WOLD/backend/run-$v" "$OUT/$v"
  else
    (cd "$NEW" && uv run python scripts/load_vt018.py "${ARGS[@]}" --out "$REL/$v" > /dev/null 2>&1); rc=$?
  fi
  echo "$v exit=$rc $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 30
done
echo DONE >> "$OUT/run-log.txt"
