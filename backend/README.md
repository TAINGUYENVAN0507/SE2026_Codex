# Backend · Vietnamese Meeting Minutes Assistant

Thư mục backend chứa ứng dụng FastAPI, database models, background worker và các API REST phục vụ hệ thống biên bản cuộc họp tiếng Việt.

## 1. Yêu cầu môi trường

- Python 3.12 (được ghim trong `.python-version`)
- [uv](https://docs.astral.sh/uv/) (trình quản lý gói và môi trường Python)

## 2. Cài đặt

Di chuyển vào thư mục `backend/` và đồng bộ môi trường với lockfile:

```bash
cd backend
uv sync --locked
```

## 3. Kiểm tra mã nguồn và chạy test

Chạy toàn bộ lint, format check và test suite trong thư mục `backend/`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Hoặc chạy kết hợp trong một dòng:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## 4. Chạy ứng dụng nội bộ (development)

```bash
uv run uvicorn app.main:app --reload --port 8000
```
