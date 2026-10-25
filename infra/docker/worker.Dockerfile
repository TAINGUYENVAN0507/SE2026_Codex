# syntax=docker/dockerfile:1.7
#
# Image worker bản CPU (AI-16). Build từ gốc repo:
#
#   docker build -f infra/docker/worker.Dockerfile -t meeting-worker:cpu .
#
# Hai venv, mỗi venv dựng từ lock của chính nó:
# - /app/backend/.venv: worker loop (`python -m app.worker.runner`), không có model.
# - /app/pipeline/.venv: extra `asr` và `diarize` (faster-whisper, pyannote, torch CPU). Worker
#   chạy subprocess của từng stage bằng interpreter này qua `PIPELINE_PYTHON`.
# Model không nằm trong image: tải vào volume `/models` (HF_HOME) lần đầu chạy, hoặc trước bằng
# `scripts/download_models.py`.

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

WORKDIR /app

# Cài dependency trước, code sau: đổi code không phải cài lại torch và model runtime.
# Bản CPU bỏ cuBLAS, cuDNN và NVRTC (khoảng 1 GB) mà extra `asr` kéo theo trên Linux.
COPY pipeline/pyproject.toml pipeline/uv.lock pipeline/README.md pipeline/
RUN --mount=type=cache,target=/root/.cache/uv \
    cd pipeline && uv sync --locked --no-dev --extra asr --extra diarize --no-install-project \
        --no-install-package nvidia-cublas-cu12 --no-install-package nvidia-cudnn-cu12 \
        --no-install-package nvidia-cuda-nvrtc-cu12

COPY backend/pyproject.toml backend/uv.lock backend/README.md backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    cd backend && uv sync --locked --no-dev --no-install-project \
        --no-install-package meeting-pipeline

COPY pipeline/ pipeline/
COPY backend/ backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    cd pipeline && uv sync --locked --no-dev --extra asr --extra diarize \
        --no-install-package nvidia-cublas-cu12 --no-install-package nvidia-cudnn-cu12 \
        --no-install-package nvidia-cuda-nvrtc-cu12 \
    && cd ../backend && uv sync --locked --no-dev

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /models /app/backend/appdata \
    && chown app:app /models /app/backend/appdata

ENV PATH="/app/backend/.venv/bin:${PATH}" \
    PIPELINE_PYTHON=/app/pipeline/.venv/bin/python \
    PIPELINE_BACKEND=real \
    ASR_DEVICE=cpu \
    ASR_COMPUTE_TYPE=int8 \
    DIARIZATION_DEVICE=cpu \
    HF_HOME=/models/huggingface

USER app
WORKDIR /app/backend
# /app/backend/appdata: file upload và artifact của job (storage của backend).
VOLUME ["/models", "/app/backend/appdata"]

CMD ["python", "-m", "app.worker.runner"]
