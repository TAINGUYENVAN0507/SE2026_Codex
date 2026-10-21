# 2026-10-21 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 10.
- **Mục tiêu:**
  - Phủ hết các endpoint còn lại của contract REST v0 (BE-02), để A làm frontend trên mock mà không phải chờ.
  - Dựng database: Postgres, Alembic và đủ các bảng (BE-03).
  - Cả hai đều nằm trên critical path tới M1.

Đọc trước: mục 7.2 (endpoints), 7.3 (ví dụ JSON) và mục "Lưu trữ" ở mục 4 của kế hoạch; [`structure/contracts.md`](../../structure/contracts.md); [`structure/architecture.md`](../../structure/architecture.md) (mục Lưu trữ, nguyên tắc dữ liệu).

Lệnh kiểm tra cho mọi commit, chạy trong `backend/`:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
uv run python scripts/generate_openapi.py   # sau khi đổi schema hoặc router, rồi commit contracts/openapi.json
```

## Bước 0: cập nhật nhánh và file hôm qua (không tính vào số commit)

```bash
git checkout haquang
git fetch origin
git merge origin/main
```

- [ ] Tick 5 ô trong `tasks/2026-10-20/member-b.md` và ghi hash: `463b64f`, `b3b31f8`, `7ce47fc`, `5bc0faf`, `79e4055`.
- [ ] Từ hôm nay **không tự merge PR**. PR #7 hôm qua do B tự merge. Theo [`rules/git-workflow.md`](../../rules/git-workflow.md), nhóm trưởng review và merge.

## Phần 1: hoàn thiện contract v0 (BE-02)

Mỗi endpoint chỉ là stub trả fixture, chưa dùng DB. Mọi fixture mới đặt ở `contracts/fixtures/api/` và phải validate được theo schema (mở rộng test drift đã có). Sau mỗi commit, sinh lại `contracts/openapi.json`.

### 1. [ ] Danh sách meeting và upload (BE-02)

- **Việc:** `GET /api/v1/meetings` có phân trang, lọc theo `status`, trả `{items, page, page_size, total}`. `POST /api/v1/meetings` nhận multipart, header `Idempotency-Key` bắt buộc (thiếu thì 400 `IDEMPOTENCY_KEY_REQUIRED`), `consent_confirmed` bắt buộc (thiếu thì 422 `CONSENT_REQUIRED`), thành công trả 201 `{meeting, job}`.
- **Fixture:** `meeting_list.json`, `meeting_created.json`.
- **Message:** `feat(contracts): meeting list and upload endpoints in contract v0 (BE-02)`
- **Hash:**

### 2. [ ] Transcript, speaker và sửa segment (BE-02)

- **Việc:** `GET /meetings/{id}/transcript` trả `{status, diarization_status, speakers, segments}`; khi `pending` thì `segments: []`. Thêm `PATCH /meetings/{id}/segments/{segment_id}` (`text`, `speaker_id`, `version`) và `PATCH /meetings/{id}/speakers/{speaker_id}` (`display_name`, `version`). Version lệch thì trả 409 `VERSION_CONFLICT` kèm `details.current`.
- **Fixture:** `transcript_ready.json` (2 speaker và 1 segment có `speaker_id: null`), `transcript_pending.json`, `error_version_conflict.json`.
- **Message:** `feat(contracts): transcript, speaker and segment edit endpoints (BE-02)`
- **Hash:**

### 3. [ ] Summary và action items (BE-02)

- **Việc:** `GET`/`PUT /meetings/{id}/summary`; `GET`/`POST /meetings/{id}/action-items`; `PATCH`/`DELETE /meetings/{id}/action-items/{item_id}`. Field theo mục 7.3 của kế hoạch: `due_date`, `due_date_text`, `assignee_name`, `assignee_speaker_id` đều có thể `null`; có `evidence_segment_ids`, `needs_review`, `source` (`ai`/`user`).
- **Fixture:** `summary_ready.json`, `summary_disabled.json`, `action_items.json` (một item có hạn, một item không có hạn).
- **Message:** `feat(contracts): summary and action item endpoints (BE-02)`
- **Hash:**

### 4. [ ] Config, auth, chạy lại job, lịch sử sửa và export (BE-02)

- **Việc:** `GET /config` (`max_upload_mb`, `max_duration_sec`, `allowed_extensions`, `export_formats`, `llm_enabled`); `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`; `POST /meetings/{id}/jobs` (`from_stage`, 409 `JOB_ALREADY_ACTIVE`); `GET /meetings/{id}/edits`; `GET /meetings/{id}/export?format=&variant=` (409 `TRANSCRIPT_NOT_READY`, 422 `FORMAT_NOT_SUPPORTED`).
- **Fixture:** `config.json`, `user_me.json`, `edits.json`.
- **Message:** `feat(contracts): config, auth, job retry, edit history and export endpoints (BE-02)`
- **Hash:**

### 5. [ ] `contracts/error_codes.md` (BE-02)

- **Việc:** bảng mã lỗi gồm mã, HTTP status, ý nghĩa và gợi ý thông điệp tiếng Việt cho frontend. Gồm mọi mã đã dùng trong contract v0, cộng mã lỗi của pipeline lấy từ enum `code` trong `contracts/pipeline/error.schema.json`. Thêm test: mọi mã trong enum đó và mọi mã backend trả ra đều có trong `error_codes.md`. Test đọc file JSON, không import package `meeting_pipeline` (ranh giới module).
- **Message:** `docs(contracts): error code catalogue for API and pipeline (BE-02)`
- **Hash:**

### 6. [ ] Workflow `contracts.yml` (BE-02)

- **Việc:** `.github/workflows/contracts.yml` chạy khi PR đổi `contracts/**`, `backend/**` hoặc `frontend/**`: test drift của OpenAPI và validate mọi fixture trong `contracts/fixtures/api/`. Hiện `backend.yml` không chạy khi chỉ `contracts/openapi.json` bị sửa tay, nên cần workflow này.
- **Xong khi:** workflow xanh trên PR. Thử sửa tay `openapi.json` ở máy thì workflow fail (không commit bản thử).
- **Message:** `ci(contracts): check OpenAPI drift and validate API fixtures (BE-02)`
- **Hash:**

## Phần 2: database (BE-03)

### 7. [ ] Postgres 16 cho dev và CI (BE-03)

- **Việc:** `docker-compose.yml` ở gốc repo, hiện chỉ có service `db` (Postgres 16, volume `pgdata`, healthcheck). `.env.example` gồm `DATABASE_URL` và các placeholder trong mục 5 của kế hoạch, không có giá trị thật. Thêm service Postgres vào `backend.yml`. Cập nhật `backend/README.md`.
- **Message:** `chore(infra): PostgreSQL 16 via docker compose for dev and CI (BE-03)`
- **Hash:**

### 8. [ ] SQLAlchemy 2, Alembic, bảng `users` và `meetings` (BE-03)

- **Việc:** thêm SQLAlchemy 2, Alembic, psycopg 3. Model `users`, `meetings` theo bảng ở mục 4 của kế hoạch (`*_at` là timestamptz UTC, có `version`). Migration đầu tiên. `/ready` ping DB thật thay vì chỉ kiểm `DATABASE_URL` có giá trị.
- **Xong khi:** test chạy `alembic upgrade head` rồi `downgrade base` trên Postgres sạch. `/ready` trả 503 khi DB tắt.
- **Message:** `feat(backend): SQLAlchemy and Alembic with users and meetings tables (BE-03)`
- **Hash:**

### 9. [ ] Bảng `jobs`: mỗi meeting chỉ 1 job đang chạy (BE-03)

- **Việc:** bảng `jobs` với các cột ở mục 4 của kế hoạch. `CHECK` cho `status`. Partial unique index `(meeting_id) WHERE status IN ('queued','running','retry_scheduled')`.
- **Xong khi:** test chứng minh insert job active thứ hai cho cùng meeting bị DB từ chối, còn job `succeeded` thì không bị chặn.
- **Message:** `feat(backend): jobs table with one active job per meeting (BE-03)`
- **Hash:**

### 10. [ ] Bảng transcript, summary, audit (BE-03)

- **Việc:** `speakers`, `segments` (`CHECK 0 <= start_sec < end_sec`, cột `ai_*`), `ai_outputs` (unique `(job_id, stage)`), `summaries`, `action_items` (xóa mềm `deleted_at`), `edit_events` (trigger Postgres chặn UPDATE, append-only), `idempotency_keys`.
- **Xong khi:** test cho từng constraint. `UPDATE edit_events` bị trigger từ chối (AUD-10, đặt tên `test_aud10_...`). Upgrade và downgrade sạch.
- **Message:** `feat(backend): transcript, summary and audit tables with integrity guards (BE-03)`
- **Hash:**

## Việc chung (không phải commit)

- [ ] SH-01: cùng nhóm ghi một buổi họp pilot 5–10 phút, ký phiếu theo `evaluation/datasets/consent_form.md`. Audio gửi cho C qua kênh riêng, **không commit**.

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash commit.
- [ ] Push `haquang`, mở PR vào `main` theo template. Phần 1 đổi contract, nên tag A (`@mactuongmvt`) để A xác nhận. **Không tự merge.**
