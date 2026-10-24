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

## 4. Cơ sở dữ liệu PostgreSQL 16 (Development & CI)

Dự án sử dụng PostgreSQL 16. Để khởi chạy cơ sở dữ liệu cho môi trường phát triển:

1. Sao chép cấu hình mẫu từ `.env.example`:
   ```bash
   cp ../.env.example ../.env
   ```
2. Khởi chạy container PostgreSQL qua Docker Compose ở thư mục gốc:
   ```bash
   docker compose up -d db
   ```
3. Kiểm tra trạng thái healthcheck của container:
   ```bash
   docker compose ps
   ```
4. Dừng cơ sở dữ liệu khi không sử dụng:
   ```bash
   docker compose down
   ```

Trên CI GitHub Actions (`.github/workflows/backend.yml`), PostgreSQL 16 được tích hợp tự động dưới dạng container service.

## 5. Chạy ứng dụng nội bộ (development)

### 5.1. Chạy API Server

Khởi chạy máy chủ FastAPI qua Uvicorn:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Tài liệu API tương tác tự động có thể truy cập tại:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 5.2. Chạy Background Worker

Worker chịu trách nhiệm claim các job ở trạng thái `queued` và thực thi pipeline xử lý âm thanh:

- Chạy worker với pipeline giả lập (fake backend, không cần model AI hay GPU):
  ```bash
  PIPELINE_BACKEND=fake uv run python -m app.worker.runner
  ```

- Chạy worker với pipeline thực (yêu cầu cài đặt thêm các extra model tương ứng trong pipeline):
  ```bash
  PIPELINE_BACKEND=real uv run python -m app.worker.runner
  ```

