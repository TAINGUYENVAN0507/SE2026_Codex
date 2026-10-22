# 2026-10-20 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh cá nhân (đề xuất `minhquang`).
- **Mục tiêu:** dựng khung `backend/` (BE-01) và bắt đầu contract REST v0 (BE-02). BE-02 nằm trên critical path tới M1, và A cần `contracts/openapi.json` để làm FE-02.

Đọc trước: [`structure/repository.md`](../../structure/repository.md) (bố cục `backend/`), [`structure/architecture.md`](../../structure/architecture.md) (API không import pipeline), [`structure/contracts.md`](../../structure/contracts.md) (quy ước dữ liệu, error envelope), [`rules/coding.md`](../../rules/coding.md).

Lệnh kiểm tra cho mọi commit, chạy trong `backend/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Bước 0: tạo nhánh (không tính vào 5 commit)

```bash
git checkout main
git pull origin main
git checkout -b minhquang
git push -u origin minhquang
```

## 5 commit

### 1. [x] Khung package `backend/` (BE-01)

- **Việc:** `backend/pyproject.toml` (uv, Python 3.12, FastAPI, pydantic-settings, pytest, httpx, ruff), `.python-version`, `uv.lock`, `backend/README.md` (cài đặt, chạy, test). Cấu hình ruff giống `pipeline/pyproject.toml`: `line-length = 100`, rule `E, F, W, I, B, UP, SIM`. Cập nhật mục `backend/` trong `structure/repository.md` nếu bố cục khác bản kế hoạch.
- **Xong khi:** `uv sync --locked` chạy được, có một test smoke import package.
- **Message:** `chore(backend): scaffold backend package with uv, ruff, pytest (BE-01)`
- **Hash:** `463b64f`

### 2. [x] App factory, settings, `/health` và `/ready` (BE-01)

- **Việc:** `app/main.py` có `create_app()`. `app/core/config.py` dùng pydantic-settings, đọc `DATABASE_URL`. Route `GET /api/v1/health` luôn trả 200. Route `GET /api/v1/ready` kiểm tra kết nối DB, không kết nối được thì trả 503. Kiểm tra DB đi qua một interface để test thay được bằng bản giả, không cần Postgres.
- **Xong khi:** có test cho `/health`, `/ready` khi DB ổn và khi DB lỗi.
- **Message:** `feat(backend): app factory, settings, health and readiness endpoints (BE-01)`
- **Hash:** `b3b31f8`

### 3. [x] Error envelope và exception handler (BE-01)

- **Việc:** mọi lỗi trả `{"error": {"code", "message", "details", "request_id"}}` đúng `structure/contracts.md`, gồm cả 404, 422 (lỗi validation của FastAPI) và 500. Lỗi 500 không trả stack trace hay message gốc của exception (`rules/privacy-security.md`).
- **Xong khi:** test cho 404, 422, 500. Test 500 dùng chuỗi canary để chứng minh message của exception không lọt ra response.
- **Message:** `feat(backend): error envelope and exception handlers (BE-01)`
- **Hash:** `7ce47fc`

### 4. [x] Log JSON có `request_id` và workflow CI (BE-01)

- **Việc:** middleware nhận header `X-Request-ID` (không có thì tự sinh), trả lại trong response, và gắn vào mọi dòng log JSON. Log chỉ ghi method, path, status, thời gian, không ghi body hay header `Authorization`. Thêm `.github/workflows/backend.yml`: chạy ruff và pytest khi PR đổi `backend/`.
- **Xong khi:** test kiểm `X-Request-ID` có trong response và trong log. Workflow xanh trên PR.
- **Message:** `feat(backend): JSON logging with request_id, backend CI workflow (BE-01)`
- **Hash:** `5bc0faf`

### 5. [x] Contract v0: schema Meeting, Job, Error và `contracts/openapi.json` (BE-02)

- **Việc:** Pydantic schema `MeetingOut`, `JobOut`, `ErrorResponse` theo mục 7.3 của kế hoạch (mọi field luôn có mặt, `snake_case`, thời điểm ISO 8601 UTC). Router stub `GET /api/v1/meetings/{id}` và `GET /api/v1/jobs/{id}` trả fixture. Lệnh sinh `contracts/openapi.json`, kèm test drift: file trong repo phải khớp với code. Thêm fixture `contracts/fixtures/api/meeting_processing.json`, `job_retry_scheduled.json`.
- **Xong khi:** `contracts/openapi.json` được commit, test drift xanh, fixture validate được theo schema. Trong PR, tag A để A xác nhận (A là consumer).
- **Message:** `feat(contracts): REST contract v0 for meetings and jobs with fixtures (BE-02)`
- **Hash:** `79e4055`

## Cuối ngày

- [x] Push nhánh và mở PR vào `main` theo template. Test evidence là output thật.
- [x] Tick các ô ở trên và ghi hash commit.
