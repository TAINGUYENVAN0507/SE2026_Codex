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

5. Chạy migration để khởi tạo hoặc cập nhật schema cơ sở dữ liệu:
   ```bash
   uv run alembic upgrade head
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

## 6. Cấu hình Môi trường và Biến Mở rộng

Hệ thống hỗ trợ các biến môi trường cấu hình kết nối và giám sát sau (tham khảo `.env.example` ở thư mục gốc):

- `WEB_CONCURRENCY` (hoặc `API_WORKERS`): Số tiến trình uvicorn worker xử lý request API (mặc định: `1`).
- `DB_RESERVED_CONNECTIONS`: Số kết nối cơ sở dữ liệu dự phòng dành riêng cho worker (claim job, heartbeat), migration và quản trị admin (mặc định: `20`). Tổng kết nối: `API_WORKERS * API_MAX_INFLIGHT + DB_RESERVED_CONNECTIONS <= POSTGRES_MAX_CONNECTIONS`.
- `PROMETHEUS_MULTIPROC_DIR`: Đường dẫn thư mục lưu trữ số liệu thống kê đa tiến trình của Prometheus client (mặc định: không đặt, chạy chế độ single-process registry).
  - Khi chạy qua Docker Compose, thư mục này được mount qua volume `promdata` vào `/tmp/prometheus_multiproc_dir` cho cả `api` và `worker` để thời lượng từng stage (`pipeline_stage_duration_seconds`) do worker xử lý được gom vào endpoint `/metrics` của API.
  - Khi chạy dev cục bộ không dùng Docker Compose mà muốn kiểm tra gom số liệu đa tiến trình, đặt cùng biến này trước khi khởi chạy cả API và worker:
    ```bash
    export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc_dir
    mkdir -p /tmp/prometheus_multiproc_dir
    ```


