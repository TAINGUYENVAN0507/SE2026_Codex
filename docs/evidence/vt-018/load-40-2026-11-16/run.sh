#!/bin/bash
# 40 client, thư mục lưu đầy (full) và rỗng (empty) xen kẽ 6 vòng, ĐỔI THỨ TỰ giữa các vòng:
# vòng lẻ full trước, vòng chẵn empty trước. DB=<URL Postgres trống> bash run.sh
# Thư mục lưu audio cứng là backend/appdata (LocalStorage), không có biến môi trường,
# nên mỗi lượt đổi appdata thành symlink tới thư mục của biến thể, xong thì trả lại.
# Từ 11-16 harness xóa file của meeting nó tạo, nên `full` giữ nguyên số thư mục qua các lượt.
set -u
: "${DB:?đặt DB=postgresql+psycopg://...}"
OUT=$(cd "$(dirname "$0")" && pwd)
cd "$OUT/../../../../backend"
REL=$(realpath --relative-to=. "$OUT")  # env.json ghi đường dẫn tương đối, không lộ thư mục máy đo
SCRATCH=${SCRATCH:-/tmp/load40-$$}        # cùng ổ đĩa với appdata
mkdir -p "$SCRATCH"
mv appdata appdata.keep
restore() { rm -f appdata; mv appdata.keep appdata; }
trap restore EXIT
for i in 1 2 3 4 5 6; do
  order="full empty"; [ $((i % 2)) = 0 ] && order="empty full"
  for v in $order; do
    target=$PWD/appdata.keep
    [ "$v" = empty ] && target=$SCRATCH/empty-$i
    mkdir -p "$target"; rm -f appdata; ln -s "$target" appdata
    echo "$v-$i $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg) audio_dirs=$(ls "$target/audio" 2>/dev/null | wc -l)" >> "$OUT/run-log.txt"
    uv run python scripts/load_vt018.py --db "$DB" --clients 40 --threshold 1.5 --out "$REL/$v-$i" > "$OUT/$v-$i.stdout" 2>&1
    echo "$v-$i exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$OUT/run-log.txt"
    sleep 15
  done
done
rm -rf "$SCRATCH"
echo DONE >> "$OUT/run-log.txt"
