# syntax=docker/dockerfile:1.7
#
# Image worker (AI-16). Build từ gốc repo:
#
#   docker build -f infra/docker/worker.Dockerfile -t meeting-worker:cpu .
#   docker build -f infra/docker/worker.Dockerfile --build-arg VARIANT=cuda -t meeting-worker:cuda .
#
# Hai venv, mỗi venv dựng từ lock của chính nó:
# - /app/backend/.venv: worker loop (`python -m app.worker.runner`), không có model.
# - /app/pipeline/.venv: extra `asr` và `diarize` (faster-whisper, pyannote, torch CPU). Worker
#   chạy subprocess của từng stage bằng interpreter này qua `PIPELINE_PYTHON`.
#
# VARIANT=cpu bỏ cuBLAS, cuDNN, NVRTC (khoảng 1 GB) mà extra `asr` kéo theo trên Linux.
# VARIANT=cuda giữ chúng: CTranslate2 nạp thư viện từ wheel `nvidia-*` (`preload_cuda_libs`),
# nên không cần base image CUDA; host chỉ cần driver NVIDIA và nvidia-container-toolkit
# (`docker run --gpus all`). Diarization vẫn chạy CPU ở cả hai bản (torch CPU).
#
# Model không nằm trong image: tải vào volume `/models` (HF_HOME) bằng
# `python -m meeting_pipeline download-models`, hoặc tự tải ở lần chạy đầu.

FROM python:3.12-slim-bookworm

ARG VARIANT=cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12

# ffmpeg lấy bản của Debian bookworm (nhận bản vá bảo mật), không ghim version.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

WORKDIR /app

# Gói bỏ qua theo VARIANT, ghi ra file để 2 lần sync bên dưới dùng chung.
RUN case "$VARIANT" in \
        cpu) printf '%s\n' --no-install-package nvidia-cublas-cu12 \
                --no-install-package nvidia-cudnn-cu12 \
                --no-install-package nvidia-cuda-nvrtc-cu12 > /app/.uv-skip ;; \
        cuda) : > /app/.uv-skip ;; \
        *) echo "VARIANT phải là cpu hoặc cuda, nhận: $VARIANT" >&2; exit 1 ;; \
    esac

# Cài dependency trước, code sau: đổi code không phải cài lại torch và model runtime.
COPY pipeline/pyproject.toml pipeline/uv.lock pipeline/README.md pipeline/
# hadolint ignore=SC2046
RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory pipeline sync --locked --no-dev --extra asr --extra diarize \
        --no-install-project $(cat /app/.uv-skip)

COPY backend/pyproject.toml backend/uv.lock backend/README.md backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory backend sync --locked --no-dev --no-install-project \
        --no-install-package meeting-pipeline

COPY pipeline/ pipeline/
COPY backend/ backend/
COPY --chmod=0755 infra/docker/worker-entrypoint.sh /usr/local/bin/worker-entrypoint
# hadolint ignore=SC2046
RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory pipeline sync --locked --no-dev --extra asr --extra diarize \
        $(cat /app/.uv-skip) \
    && uv --directory backend sync --locked --no-dev

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /models /app/backend/appdata \
    && chown app:app /models /app/backend/appdata

# ASR_DEVICE và ASR_COMPUTE_TYPE do entrypoint đặt theo WORKER_VARIANT nếu chưa có.
ENV PATH="/app/backend/.venv/bin:${PATH}" \
    WORKER_VARIANT=${VARIANT} \
    PIPELINE_PYTHON=/app/pipeline/.venv/bin/python \
    PIPELINE_BACKEND=real \
    DIARIZATION_DEVICE=cpu \
    HF_HOME=/models/huggingface

USER app
WORKDIR /app/backend
# /app/backend/appdata: file upload và artifact của job (storage của backend).
VOLUME ["/models", "/app/backend/appdata"]

ENTRYPOINT ["worker-entrypoint"]
CMD ["python", "-m", "app.worker.runner"]
