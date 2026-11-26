#!/bin/bash
# 247 client, 2 process API, --search 4, thư mục lưu trống; ba bản app xen kẽ ABCCBA ABCCBA, 12 lượt:
#   pre75  = b35e06f (trước #75)
#   post75 = 70b527a (sau #75, trước #78)
#   main   = main sau #77, #78 (db8072b; working tree có thêm commit test của C, backend/app như db8072b)
# Harness (backend/scripts) và uv.lock giống hệt ở ba bản.
# W35=<worktree b35e06f> W70=<worktree 70b527a> DB=<URL Postgres trống> bash run.sh
# Lượt của worktree chạy với --out tương đối trong worktree rồi chép về đây, để env.json không ghi
# đường dẫn của máy đo.
set -u
: "${DB:?}" "${W35:?}" "${W70:?}"
OUT=$(cd "$(dirname "$0")" && pwd)
NEW="$OUT/../../../../backend"
REL=$(cd "$NEW" && realpath --relative-to=. "$OUT")
i=0
for app in pre75 post75 main main post75 pre75 pre75 post75 main main post75 pre75; do
  i=$((i + 1))
  v=$app-$i
  echo "$v $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  case $app in
    pre75) WT=$W35 ;;
    post75) WT=$W70 ;;
    *) WT= ;;
  esac
  ARGS=(--db "$DB" --clients 247 --threshold 2.0 --api-workers 2 --client-procs 4 --search 4)
  if [ -n "$WT" ]; then
    (cd "$WT/backend" && rm -rf "run-$v" && uv run python scripts/load_vt018.py "${ARGS[@]}" \
      --out "run-$v" > "$OUT/$v.stdout" 2>&1); rc=$?
    cp -r "$WT/backend/run-$v" "$OUT/$v"
  else
    (cd "$NEW" && uv run python scripts/load_vt018.py "${ARGS[@]}" --out "$REL/$v" \
      > "$OUT/$v.stdout" 2>&1); rc=$?
  fi
  echo "$v exit=$rc $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
  sleep 30
done
echo DONE >> "$OUT/run-log.txt"
