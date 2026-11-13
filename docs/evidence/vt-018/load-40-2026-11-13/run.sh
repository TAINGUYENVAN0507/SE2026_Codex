#!/bin/bash
cd "$(dirname "$0")/../../../../backend"
OUT=../docs/evidence/vt-018/load-40-2026-11-13
mkdir -p $OUT
for i in 1 2 3 4 5 6; do
  for v in real stub; do
    if [ $v = stub ]; then export FFPROBE_BIN=$PWD/../docs/evidence/vt-018/load-40-2026-11-13/ffprobe-stub.sh; else unset FFPROBE_BIN; fi
    echo "$v-$i $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> $OUT/run-log.txt
    uv run python scripts/load_vt018.py --db postgresql+psycopg://<url> --clients 40 --threshold 1.5 --out $OUT/$v-$i > $OUT/$v-$i.stdout 2>&1
    echo "$v-$i exit=$? $(date +%T) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> $OUT/run-log.txt
    sleep 15
  done
done
echo DONE >> $OUT/run-log.txt
