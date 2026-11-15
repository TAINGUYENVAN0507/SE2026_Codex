#!/bin/bash
# 40 client, 4 biến thể xen kẽ, 4 vòng. DB=<URL Postgres trống> bash run.sh
# Thư mục lưu audio cứng là backend/appdata (LocalStorage), không có biến môi trường,
# nên mỗi lượt đổi appdata thành symlink tới thư mục của biến thể, xong thì trả lại.
set -u
: "${DB:?đặt DB=postgresql+psycopg://...}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
SCRATCH=${SCRATCH:-/tmp/load40-$$}
mkdir -p "$SCRATCH"
mv appdata appdata.keep
restore() { rm -f appdata; mv appdata.keep appdata; }
trap restore EXIT
for i in 1 2 3 4; do
  for v in base nosync fresh tmpfs; do
    url=$DB; target=$PWD/appdata.keep
    case $v in
      nosync) url="$DB?options=-csynchronous_commit%3Doff" ;;
      fresh) target=$SCRATCH/fresh-$i ;;                 # thư mục rỗng, cùng ổ đĩa
      tmpfs) target=/dev/shm/load40-$$-tmpfs-$i ;;       # thư mục rỗng, trên RAM
    esac
    mkdir -p "$target"; rm -f appdata; ln -s "$target" appdata
    echo "$v-$i $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg) audio_dirs=$(ls "$target/audio" 2>/dev/null | wc -l)" >> "$OUT/run-log.txt"
    uv run python scripts/load_vt018.py --db "$url" --clients 40 --threshold 1.5 --out "$REL/$v-$i" > "$OUT/$v-$i.stdout" 2>&1
    echo "$v-$i exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    sleep 15
  done
done
rm -rf /dev/shm/load40-$$-tmpfs-* "$SCRATCH"
echo DONE >> "$OUT/run-log.txt"
