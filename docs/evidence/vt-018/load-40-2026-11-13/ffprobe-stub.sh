#!/bin/sh
# ffprobe giả cho chẩn đoán tải: in JSON mà ffprobe thật in ra cho WAV im lặng 3 s
# của harness, không đọc file. Dùng: FFPROBE_BIN=<đường dẫn tới file này>.
cat "$(dirname "$0")/ffprobe-stub.json"
