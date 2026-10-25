#!/bin/sh
# Đặt mặc định cho ASR theo bản image (AI-16), rồi chạy lệnh được truyền vào.
# Biến đã đặt khi `docker run -e ...` thì giữ nguyên.
set -eu

if [ "${WORKER_VARIANT:-cpu}" = cuda ]; then
    : "${ASR_DEVICE:=cuda}" "${ASR_COMPUTE_TYPE:=int8_float16}"
else
    : "${ASR_DEVICE:=cpu}" "${ASR_COMPUTE_TYPE:=int8}"
fi
export ASR_DEVICE ASR_COMPUTE_TYPE

exec "$@"
