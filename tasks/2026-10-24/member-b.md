# 2026-10-24 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Mục tiêu:** sửa các lỗi tìm ra khi review PR #20, rồi bắt đầu Edit APIs (BE-11) để phần sửa segment, speaker và tóm tắt của A (FE-10, FE-11, FE-12) chạy với backend thật.

Đọc trước:
- Mục BE-08, BE-10, BE-11 và mục 7.1 (`version`, 409 `VERSION_CONFLICT`) của kế hoạch.
- `pipeline/README.md`, mục "Gọi pipeline từ worker": `run_job` có thêm `on_heartbeat` (PR của C hôm nay).
- [`rules/privacy-security.md`](../../rules/privacy-security.md), mục log và thông điệp lỗi.

Lệnh kiểm tra cho mọi commit, chạy trong `backend/` (cần Postgres: `docker compose up -d db` ở gốc repo):

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Bước 0 (không tính vào số commit)

```bash
git checkout haquang
git fetch origin
git merge origin/main
```

- PR #20 đã được merge (`044601d`). Commit 1 cần `on_heartbeat` của pipeline: merge `main` sau khi PR AI-04 của C hôm nay đã vào.
- [ ] **Tiêu đề PR theo format commit.** PR #20 vẫn có tiêu đề "Haquang" (giống #7, #10, #16). Ví dụ cho hôm nay: `fix(backend): lease heartbeat, safe defaults and first edit APIs (BE-08, BE-11)`.

## Phần 0: sửa lỗi tìm ra khi review PR #20

### 1. [x] Heartbeat gia hạn lease, reaper chạy trong worker (BE-08)

- **Lỗi:**
  - `heartbeat_job()`, `reap_expired_jobs()` và `release_job_on_sigterm()` trong `app/worker/reaper.py` mới chỉ có test, worker chưa gọi hàm nào.
  - `process_job()` chỉ cập nhật `heartbeat_at` khi có progress (`runner.py:113`), không gia hạn `locked_until`. Lease 60 s hết hạn ngay khi job chạy quá 1 phút.
  - Khi reaper được bật, job dài sẽ bị requeue trong lúc vẫn đang chạy. Diarization trên CPU mất khoảng 46' cho audio 60', và có thể không có progress trong nhiều phút.
- **Việc:**
  - Truyền `on_heartbeat=lambda: heartbeat_job(db, job)` vào `run_job()`. Pipeline gọi callback này mỗi 15 s, kể cả khi stage đang chạy, trên đúng thread của worker.
  - `run_worker_loop` gọi `reap_expired_jobs()` mỗi 30 s.
  - SIGTERM giữa chừng: dừng job đang chạy (`is_cancelled` trả `True`, pipeline kill stage trong 1 s), rồi `release_job_on_sigterm()`, không tăng `attempt`.
- **Xong khi:** test bằng clock giả:
  - job chạy 3 phút với `FAKE_STAGE_SLEEP_SEC` vẫn giữ lease;
  - worker chết (không heartbeat) thì reaper requeue;
  - SIGTERM thì job về `queued` với `attempt` giữ nguyên (RT-09).
- **Message:** `fix(backend): heartbeat extends the lease and the reaper runs in the worker (BE-08)`
- **Hash:** 59bedd1

### 2. [x] Giá trị mặc định an toàn (BE-09, BE-10)

- **Lỗi:**
  - `runner.py:60` và `:256`: không đặt `PIPELINE_BACKEND` thì worker dùng `fake`. Máy chạy thật thiếu biến này sẽ âm thầm ghi transcript giả. Pipeline cố tình mặc định `real` vì lý do này.
  - `config.py:19`: `MAX_DURATION_SEC = 7200`, nhưng pipeline giới hạn 3600 (`PIPELINE_MAX_DURATION_SEC`, P0 của kế hoạch là 60'). File dài 61–120' qua được upload rồi mới fail ở preprocess.
  - `config.py:22`: `JWT_SECRET` có giá trị mặc định nằm trong repo public. Chạy production mà quên đặt biến thì ai cũng ký được token.
- **Việc:**
  - Worker truyền `backend=None` khi không đặt `PIPELINE_BACKEND`, để pipeline tự chọn `real`.
  - `MAX_DURATION_SEC` mặc định 3600; worker truyền cùng giá trị sang pipeline qua `env={"PIPELINE_MAX_DURATION_SEC": ...}`.
  - `ENVIRONMENT=production` mà `JWT_SECRET` là giá trị mặc định hoặc ngắn hơn 32 ký tự thì app không khởi động, báo lỗi rõ ràng.
- **Xong khi:** test cho cả 3 trường hợp.
- **Message:** `fix(backend): safe defaults for pipeline backend, duration limit and JWT secret (BE-09, BE-10)`
- **Hash:** 80821fd

### 3. [x] Thông điệp lỗi không chứa nội dung artifact (BE-07)

- **Lỗi:**
  - `persister.py:64, 83, 193, 210` đưa `{exc}` vào message. `str(ValidationError)` của pydantic có `input_value`, tức là một phần text của transcript.
  - `:54, :183` lộ đường dẫn trên server.
  - Message này được ghi vào `job.error_message`, trả ra ở `GET /jobs/{id}` và ghi vào log (`logger.error(... err)`). [`rules/privacy-security.md`](../../rules/privacy-security.md) cấm log nội dung transcript.
- **Việc:** chỉ ghi số lỗi (`exc.error_count()`) và tên file artifact, không ghi đường dẫn đầy đủ. Xem cách làm trong `pipeline/meeting_pipeline/stages/base.py`.
- **Xong khi:** test dùng transcript chứa một chuỗi canary (ví dụ `CANARY_7f3a`) và sai schema: chuỗi này không có trong `job.error_message`, response của API và log (`caplog`).
- **Message:** `fix(backend): pipeline persist errors never echo artifact contents (BE-07)`
- **Hash:** fea1281

## Phần 1: Edit APIs (BE-11)

Endpoint nào cũng phải có `CurrentUser` và lọc theo owner (meeting của người khác thì 404), có optimistic locking bằng `version` (lệch thì 409 `VERSION_CONFLICT` kèm bản hiện tại). Cập nhật không đổi giá trị thì trả 200 và không tăng `version`. Hiện các endpoint này vẫn là stub trả fixture và không kiểm tra đăng nhập.

### 4. [x] `PATCH /meetings/{id}/segments/{segment_id}` thật (BE-11)

- **Việc:**
  - Sửa `text` (1–5000 ký tự, bỏ khoảng trắng hai đầu) và/hoặc `speaker_id` (speaker của cùng meeting, hoặc `null` là "Chưa xác định"; speaker của meeting khác thì 422 `SPEAKER_NOT_IN_MEETING`).
  - Giữ nguyên `ai_text`, `ai_speaker_id`. `is_edited` trong response là `true` khi `text` hoặc `speaker_id` khác bản AI.
  - Ghi `edit_events` trong cùng transaction (before, after, actor, `entity_version_after`).
- **Xong khi:** API test: happy path, 422 (text rỗng hoặc quá dài, speaker của meeting khác), 409, 404 (của người khác), cập nhật không đổi giá trị.
- **Message:** `feat(backend): segment edits with optimistic locking and edit events (BE-11)`
- **Hash:** 14d6222

### 5. [x] `PATCH /speakers/{id}` và `PUT /summary` thật (BE-11)

- **Việc:**
  - Đổi `display_name` của speaker: 1–50 ký tự, không trùng trong cùng meeting (so sánh không phân biệt hoa thường; trùng thì 422 `SPEAKER_NAME_DUPLICATE`).
  - `PUT /summary`: sửa overview, key points, decisions, kèm `version`. Giữ bản AI gốc trong `ai_outputs`.
  - Cả hai đều ghi `edit_events`.
- **Xong khi:** API test cho từng endpoint: happy path, 422, 409, 404.
- **Message:** `feat(backend): speaker rename and summary update with versions (BE-11)`
- **Hash:** ad07b24

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [x] Tick các ô ở trên và ghi hash. Làm không hết thì ghi rõ commit nào chuyển sang ngày sau.
- [ ] Push `haquang`, mở PR vào `main`, tiêu đề theo format commit. **Không tự merge.** Nếu đổi `contracts/openapi.json` thì commit cả `frontend/src/api/schema.d.ts`.
