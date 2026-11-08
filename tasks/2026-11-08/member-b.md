# 2026-11-08 · Member B: tách controller, privacy, độ tin cậy (Đợt 3)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #38 và #39 đã vào `main`.
- **Mục tiêu:** `meetings.py` nhỏ hơn (hiện 1940 dòng, 14 route); test privacy và reliability; `make`.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 3. Kiểm tra trong `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Trên máy có `ffprobe` thật, 5 test upload lỗi `AUDIO_INVALID` từ trước (không phải do thay đổi của bạn; CI xanh).

## Việc đầu tiên (không tính commit): review PR của C
C mở PR `tainguyen` hôm nay (ADR 0002, test canary log của pipeline, đồng bộ README, đo tải 239 và 247). Ghi nhận xét thật vào PR; kiểm riêng: con số tải có khớp `docs/evidence/` và có ghi giới hạn phép đo không.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [x] Tách route segment và key point khỏi `meetings.py` (BE-12)
- Chuyển nguyên route sang module riêng, **không đổi hành vi**. Test drift OpenAPI không đổi; ghi số dòng trước/sau:
  - `meetings.py`: từ 1940 dòng giảm xuống 1508 dòng (giảm 432 dòng).
  - Tách `PATCH /{meeting_id}/segments/{segment_id}` sang `backend/app/api/v1/segments.py`.
  - Tách `GET, PUT /{meeting_id}/summary` sang `backend/app/api/v1/summary.py`.
  - Giữ nguyên thứ tự đăng ký router, 0 drift OpenAPI (`test_openapi_drift.py` 46 passed).
- **Commit:** `615eb26`
- **Message:** `refactor(backend): move segment and key point routes out of meetings.py (BE-12)`

### 2. [x] Tách route export và job khỏi `meetings.py`; bỏ `serialize_job` lặp (BE-12)
- Dùng một `serialize_job` duy nhất trong `backend/app/api/v1/jobs.py` (bỏ lặp code giữa `meetings.py` và `jobs.py`).
- Tách `GET /{meeting_id}/export` sang `backend/app/api/v1/export.py`.
- Tách `POST /{meeting_id}/jobs` sang `backend/app/api/v1/jobs.py` (`meeting_jobs_router`).
- `meetings.py` giảm tiếp từ 1508 dòng xuống 1216 dòng (tổng cộng giảm 724 dòng từ 1940 dòng).
- **Commit:** `f5622da`
- **Message:** `refactor(backend): move export and job routes, share serialize_job (BE-12)`

### 3. [x] `tests/privacy`: canary không lọt vào log và DB sau khi xóa (BE-18, BE-19)
- Xây dựng bộ test `backend/tests/privacy/test_privacy_canary.py` (3 passed).
- Tiêu đề/transcript/summary canary đi qua upload → xử lý worker → edit → xóa (`erase_meeting`, `erase_user`).
- Quét toàn bộ các bảng trong `Base.metadata` và toàn bộ tệp trong storage, khẳng định 0 canary còn sót lại.
- Log API và worker tuân thủ JSON format, tuyệt đối không chứa canary.
- **Commit:** `da2d144`
- **Message:** `test(backend): privacy canary across API and worker logs and tables (BE-18, BE-19)`

### 4. [x] `tests/reliability` và `docs/evidence/` (BE-15)
- Bộ test `backend/tests/reliability/test_reliability_scenarios.py` (3 passed).
- 3 kịch bản: worker chết giữa chừng (reaper lấy lại, tăng attempt, worker mới xử lý thành công), retry cạn kiệt lượt (chuyển sang `failed`), tải lên trùng khóa Idempotency (`Idempotent-Replayed: true`, không tạo bản ghi thừa).
- Bằng chứng thực nghiệm ghi nhận tại `docs/evidence/reliability.md` với output terminal thật.
- **Commit:** `3f6c7ad`
- **Message:** `test(backend): reliability scenarios with recorded evidence (BE-15)`

### 5. [x] `Makefile`: `make test`, `make lint`, `make up`, `make down` (BE-16)
- Makefile tại thư mục gốc với các target: `test`, `lint`, `up`, `down`, `openapi`, `check-openapi`.
- Mỗi target gọi đúng lệnh đã ghi trong README; README cập nhật trỏ tới `make`.
- **Commit:** `3c3ae9a`
- **Message:** `chore(infra): Makefile for test, lint and compose (BE-16)`

## Việc thêm nếu còn thời gian (ngoài 5 commit)
- Đo tải 247 của C **không đạt** (p95 63 s, 155 × 503), chưa rõ nguyên nhân: xem `docs/evidence/load-247/analysis.md`. Profile `POST /meetings` (thời gian giữ kết nối DB, `ffprobe`), thử `uvicorn --workers N`, rồi chạy lại `backend/scripts/load_vt018.py --clients 247 --threshold 2.0`. Ghi số thật, kể cả khi vẫn không đạt.

## Cuối ngày
- [x] Tick và ghi hash. Push `haquang`, mở PR vào `main`. **Không tự merge.**
- **Commit sửa lỗi CI (BE-18, BE-19):** `1bc65b1` - `fix(backend): prevent alembic migrations from disabling application loggers (BE-18, BE-19)`: Sửa `alembic/env.py`, `conftest.py` và `logging.py` để fileConfig trong migration không vô hiệu hóa loggers của worker/API khi test trên Postgres ở CI.
- **Commit sửa lỗi CI Docker (BE-16):** `75f987a` - `fix(infra): copy openapi contract for vite build in web dockerfile (BE-16)`: Bổ sung copy contracts/openapi.json vào builder stage của infra/docker/web.Dockerfile để frontend/vite.config.ts đọc contract khi chạy npx vite build trong Docker buildx.
