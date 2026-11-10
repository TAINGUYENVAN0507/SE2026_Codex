# syntax=docker/dockerfile:1.7
#
# Dockerfile cho API backend (kèm worker) (BE-16).
# Build từ gốc repo:
#   docker build -f infra/docker/api.Dockerfile -t meeting-api .
#
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12

# Cài đặt ffmpeg cho xử lý audio và curl cho healthcheck
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

WORKDIR /app

# Cài đặt dependency theo layer để tối ưu cache
COPY pipeline/pyproject.toml pipeline/uv.lock pipeline/README.md pipeline/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory pipeline sync --locked --no-dev --no-install-project

COPY backend/pyproject.toml backend/uv.lock backend/README.md backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory backend sync --locked --no-dev --no-install-project \
        --no-install-package meeting-pipeline

# Copy toàn bộ mã nguồn backend và pipeline
COPY pipeline/ pipeline/
COPY backend/ backend/

# Cài đặt hoàn thiện các gói vào virtualenv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory pipeline sync --locked --no-dev \
    && uv --directory backend sync --locked --no-dev

# Tạo user không phải root (UID 10001) và cấp quyền thư mục appdata
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/backend/appdata \
    && chown -R app:app /app

ENV PATH="/app/backend/.venv/bin:${PATH}" \
    PYTHONPATH=/app/backend \
    STORAGE_DIR=/app/backend/appdata

USER app
WORKDIR /app/backend

VOLUME ["/app/backend/appdata"]

EXPOSE 8000

# Mặc định khởi chạy API server với số worker từ API_WORKERS (mặc định 1) (AD-018, BE-16)
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers \"${API_WORKERS:-1}\""]

