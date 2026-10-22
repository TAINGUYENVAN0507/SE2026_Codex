# 2026-10-22 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Mục tiêu:**
  - Làm nốt 3 commit database (BE-03) chuyển từ hôm qua.
  - Thêm seed dữ liệu (BE-03) và service lưu file upload (phần đầu BE-04).
  - Upload thật (BE-04) và worker (BE-06) cần các bảng này, và cả hai nằm trên critical path tới M1.

Đọc trước: mục 4 (Lưu trữ) và mục 6.2 (BE-03, BE-04) của kế hoạch; [`structure/architecture.md`](../../structure/architecture.md) (mục Lưu trữ, nguyên tắc dữ liệu); [`rules/privacy-security.md`](../../rules/privacy-security.md).

Lệnh kiểm tra cho mọi commit, chạy trong `backend/`:

```bash
docker compose up -d db   # ở gốc repo
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Bước 0 (không tính vào số commit)

```bash
git checkout haquang
git fetch origin
git merge origin/main
```

- [x] Tick và ghi hash cho các commit đã làm trong `tasks/2026-10-20/member-b.md` (5 commit) và `tasks/2026-10-21/member-b.md` (commit 1–7: `7032240`, `5bd251f`, `20ffa8d`, `2b8bef5`, `3a61b30`, `dff4ae4`, `2d0bcc1`).
- [x] PR #10 có tiêu đề "Haquang". Từ nay đặt tiêu đề PR theo format commit, ví dụ `feat(backend): database tables and seed (BE-03)`.
- [x] `main` có sửa `.env.example` (PR #12): `FAKE_SCENARIO=ok`, các biến `ASR_*` theo ADR-0001. Giữ bản đó.
- [x] Từ nay PR nào đổi `contracts/openapi.json` thì chạy luôn `npm ci && npm run gen:api` trong `frontend/` và commit `frontend/src/api/schema.d.ts` cùng PR. Nếu không, CI frontend trên `main` sẽ đỏ, như đã xảy ra sau PR #10.

## 5 commit

### 1. [x] SQLAlchemy 2, Alembic, bảng `users` và `meetings` (BE-03, chuyển từ 2026-10-21)

- **Việc:** thêm SQLAlchemy 2, Alembic, psycopg 3. Model `users`, `meetings` theo mục 4 của kế hoạch (`*_at` là timestamptz UTC, có `version`). Viết migration đầu tiên. `/ready` ping DB thật.
- **Xong khi:** test `alembic upgrade head` rồi `downgrade base` trên Postgres sạch; `/ready` trả 503 khi DB tắt.
- **Message:** `feat(backend): SQLAlchemy and Alembic with users and meetings tables (BE-03)`
- **Hash:** `06ba08f`

### 2. [x] Bảng `jobs`: mỗi meeting chỉ 1 job đang chạy (BE-03, chuyển từ 2026-10-21)

- **Việc:** `CHECK` cho `status`. Partial unique index `(meeting_id) WHERE status IN ('queued','running','retry_scheduled')`.
- **Xong khi:** test: insert job active thứ hai bị DB từ chối, job `succeeded` thì không bị chặn.
- **Message:** `feat(backend): jobs table with one active job per meeting (BE-03)`
- **Hash:** `3ee688c`

### 3. [x] Bảng transcript, summary, audit (BE-03, chuyển từ 2026-10-21)

- **Việc:** `speakers`, `segments` (`CHECK 0 <= start_sec < end_sec`, cột `ai_*`), `ai_outputs` (unique `(job_id, stage)`), `summaries`, `action_items` (xóa mềm), `edit_events` (trigger chặn UPDATE), `idempotency_keys`.
- **Xong khi:** test cho từng constraint; `test_aud10_...` chứng minh `UPDATE edit_events` bị từ chối; upgrade và downgrade sạch.
- **Message:** `feat(backend): transcript, summary and audit tables with integrity guards (BE-03)`
- **Hash:** `6cb75fc`

### 4. [x] Lệnh seed (BE-03)

- **Việc:** `uv run python -m app.scripts.seed` tạo 1 user demo (mật khẩu đọc từ biến môi trường, không hard-code), 1 meeting `ready` với 2 speaker, vài segment (có 1 segment `speaker_id = null`), summary và 2 action item, nội dung lấy theo `contracts/fixtures/api/transcript_ready.json`. Chạy lại nhiều lần không tạo bản trùng.
- **Xong khi:** test chạy seed 2 lần, số row không đổi.
- **Message:** `feat(backend): idempotent seed command with a demo meeting (BE-03)`
- **Hash:** `74b35ed`

### 5. [x] Service lưu file upload (BE-04, phần đầu)

- **Việc:** `app/services/storage/`: interface `Storage` cùng bản lưu ở ổ đĩa local. Ghi file upload theo từng chunk 1 MB vào file tạm, tính sha256 trong lúc ghi; vượt `MAX_UPLOAD_MB` thì dừng, xóa file tạm và báo lỗi `FILE_TOO_LARGE`; xong thì move atomic vào `audio/{meeting_id}/original.<ext>`. Chưa nối vào router.
- **Xong khi:** test: file nhỏ ghi đúng nội dung và sha256; file vượt giới hạn không để lại file rác; lỗi giữa chừng cũng không để lại file tạm.
- **Message:** `feat(backend): chunked upload storage with size limit and sha256 (BE-04)`
- **Hash:** `5901de2`

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (chưa làm hôm qua).

## Cuối ngày

- [x] Tick các ô ở trên và ghi hash.
- [ ] Push `haquang`, mở PR vào `main`, tiêu đề theo format commit. **Không tự merge.**
