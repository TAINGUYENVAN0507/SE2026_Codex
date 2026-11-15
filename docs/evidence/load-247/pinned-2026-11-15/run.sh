#!/bin/bash
# 247 client, xen kẽ chung CPU / tách CPU, 1 và 4 process API, 3 vòng.
# DB=<URL Postgres trống> PGDATA=<thư mục cluster> bash run.sh
# Máy 6 nhân × 2 luồng; luồng anh em là (k, k+6). Server (API, worker, Postgres): nhân 0-3
# = CPU 0-3,6-9. Máy sinh tải: nhân 4-5 = CPU 4,5,10,11. Chia theo nhân vật lý để hai bên
# không chung một nhân qua hyper-threading.
set -u
: "${DB:?}" "${PGDATA:?}"
SERVER=0-3,6-9
CLIENT=4,5,10,11
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
pin_pg() {  # Postgres chạy ngoài harness: ghim postmaster và mọi process con; backend mới kế thừa.
  local pm; pm=$(head -1 "$PGDATA/postmaster.pid")
  for p in $pm $(pgrep -P "$pm"); do taskset -a -cp "$1" "$p" > /dev/null; done
}
for i in 1 2 3; do
  for v in shared-1 pinned-1 shared-4 pinned-4; do
    workers=${v#*-}; extra=(); inflight=()
    [ "$workers" = 4 ] && inflight=(env API_MAX_INFLIGHT=20)
    if [ "${v%-*}" = pinned ]; then
      pin_pg $SERVER; extra=(--server-cpus $SERVER --client-cpus $CLIENT)
    else
      pin_pg 0-11
    fi
    echo "$v-$i $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    "${inflight[@]}" uv run python scripts/load_vt018.py --db "$DB" --clients 247 --threshold 2.0 \
      --api-workers "$workers" --client-procs 4 "${extra[@]}" --out "$REL/$v-$i" > "$OUT/$v-$i.stdout" 2>&1
    echo "$v-$i exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    sleep 15
  done
done
pin_pg 0-11
echo DONE >> "$OUT/run-log.txt"
