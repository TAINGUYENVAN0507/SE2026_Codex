# 2026-10-23 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 20.
- **Mục tiêu:** đưa backend tới mốc **M1**: upload từ UI, backend lưu file, tạo meeting và job, worker chạy fake pipeline, persist transcript, UI thấy trạng thái đổi và đọc được transcript. Thứ tự các phần dưới đây theo phụ thuộc: sửa lỗi review, auth, upload, API đọc, worker, persist, độ tin cậy, test tích hợp.

Đọc trước: mục 4 (vòng đời job, timeout và retry, lưu trữ), mục 6.2 (BE-04 đến BE-09) và mục 10.4 (RT-01…15, PRIV-10…17) của kế hoạch; [`structure/architecture.md`](../../structure/architecture.md) (ranh giới: chỉ worker được import `meeting_pipeline`, và chỉ dùng `run_job`, `JobSpec`, `errors`); `pipeline/README.md` mục "Gọi pipeline từ worker".

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

- [ ] Tiêu đề PR theo format commit. PR #7, #10, #16 đều có tiêu đề "Haquang". Ví dụ hôm nay: `feat(backend): auth, real upload, worker with fake pipeline (BE-04…BE-09)`.

## Phần 0: sửa 2 lỗi phát hiện khi review PR #16

### 1. [ ] Hash mật khẩu bằng argon2, bỏ mật khẩu demo viết cứng (BE-09)

- **Việc:** `app/core/security.py`: `hash_password()`, `verify_password()` dùng `argon2-cffi`. Hiện `seed.py` dùng một lần SHA-256 không salt nhưng gắn nhãn `pbkdf2_sha256`, và có mật khẩu mặc định `demo_password_2026` trong code. Seed bắt buộc có biến `SEED_DEMO_PASSWORD`; không có thì báo lỗi rõ ràng, không tự đặt mật khẩu.
- **Xong khi:** test: hash có salt (hash 2 lần cùng mật khẩu ra 2 chuỗi khác nhau), verify đúng và sai; seed không có biến môi trường thì báo lỗi.
- **Message:** `fix(backend): hash passwords with argon2, require the seed password from env (BE-09)`
- **Hash:**

### 2. [ ] Test database không được âm thầm chuyển sang SQLite (BE-03)

- **Việc:** hiện `test_database_migrations.py`, `test_integrity_guards.py` không kết nối được Postgres thì âm thầm chạy SQLite. Khi đó partial unique index và trigger của Postgres không được kiểm thật mà test vẫn xanh. Gom lại thành một fixture trong `tests/conftest.py`: không có Postgres thì `pytest.skip("cần Postgres: docker compose up -d db")` khi chạy ở máy, và `pytest.fail` khi biến `CI=true`.
- **Xong khi:** máy không chạy Docker thì các test này hiện skip kèm lý do; trên CI, chúng chạy với Postgres.
- **Message:** `test(backend): skip database tests without Postgres locally, fail on CI (BE-03)`
- **Hash:**

## Phần 1: auth (BE-09)

### 3. [ ] Login, logout, me với cookie JWT HttpOnly (BE-09)

- **Việc:** thay stub ở `api/v1/auth.py` bằng bản thật: kiểm user trong DB bằng `verify_password`, JWT (PyJWT) trong cookie `HttpOnly; SameSite=Lax` (`Secure` khi chạy prod), `JWT_SECRET` đọc từ env. Sai mật khẩu thì 401 `INVALID_CREDENTIALS`, không nói rõ là sai email hay sai mật khẩu.
- **Xong khi:** test login thành công/thất bại, cờ của cookie, `GET /auth/me` có cookie và không có cookie (401).
- **Message:** `feat(backend): login, logout and me with an HttpOnly JWT cookie (BE-09)`
- **Hash:**

### 4. [ ] Dependency user hiện tại, lọc theo owner, 404 cho tài nguyên của người khác (BE-09)

- **Việc:** dependency `current_user` dùng cho mọi route `/meetings/**` và `/jobs/**`. Mọi truy vấn lọc theo `owner_id`; tài nguyên của user khác trả 404, không trả 403.
- **Xong khi:** test PRIV-12 (`test_priv12_...`): chưa đăng nhập thì 401, user B truy cập meeting của user A thì 404.
- **Message:** `feat(backend): current user dependency and owner scoping (BE-09)`
- **Hash:**

### 5. [ ] CLI tạo user (BE-09)

- **Việc:** `uv run python -m app.scripts.create_user --email ... --name ...`, mật khẩu nhập từ prompt hoặc stdin, không nhận qua tham số dòng lệnh (sẽ lộ trong lịch sử shell).
- **Xong khi:** test tạo user, email trùng thì báo lỗi.
- **Message:** `feat(backend): create-user command reading the password from a prompt (BE-09)`
- **Hash:**

## Phần 2: upload thật (BE-04)

### 6. [ ] Service idempotency (BE-04)

- **Việc:** `app/services/idempotency/`: theo `(user_id, key, endpoint)`: chưa có thì ghi trạng thái đang xử lý; đang xử lý thì trả 409 `REQUEST_IN_PROGRESS`; đã xong thì trả lại đúng response cũ kèm header `Idempotent-Replayed: true`. TTL 24 giờ.
- **Xong khi:** test 3 nhánh và test hết hạn TTL (dùng clock giả).
- **Message:** `feat(backend): idempotency service for POST requests (BE-04)`
- **Hash:**

### 7. [ ] Kiểm tra audio bằng ffprobe (BE-04)

- **Việc:** whitelist đuôi file và MIME (sai thì 415 `UNSUPPORTED_MEDIA_TYPE`); `ffprobe` có timeout, file không có audio stream thì 422 `AUDIO_INVALID`. Không tin MIME do client gửi.
- **Xong khi:** test với file sinh bằng ffmpeg lúc chạy test: wav hợp lệ, file `.txt` đổi đuôi thành `.mp3` (422), đuôi lạ (415).
- **Message:** `feat(backend): validate uploads with an extension whitelist and ffprobe (BE-04)`
- **Hash:**

### 8. [ ] `POST /meetings` thật (BE-04)

- **Việc:** nối storage (đã có), kiểm tra audio, idempotency: ghi file theo chunk, tạo meeting và job `queued` **trong 1 transaction**, trả 201 `{meeting, job}`. Lỗi ở bất kỳ bước nào thì không để lại file rác hay row thừa. `consent_confirmed` bắt buộc.
- **Xong khi:** test happy path, 413, 422 `CONSENT_REQUIRED`, lỗi DB giả lập giữa transaction (không còn file trên đĩa).
- **Message:** `feat(backend): real meeting upload in one transaction (BE-04)`
- **Hash:**

### 9. [ ] RT-07: upload lặp lại cùng `Idempotency-Key` (BE-04)

- **Việc:** test gửi tuần tự và song song (2 thread) cùng key.
- **Xong khi:** chỉ có 1 meeting và 1 file trên đĩa; mọi response giống nhau.
- **Message:** `test(backend): RT-07 repeated uploads with one idempotency key (BE-04)`
- **Hash:**

## Phần 3: API đọc từ DB (BE-05)

### 10. [ ] `GET /meetings` và `GET /meetings/{id}` từ DB (BE-05)

- **Việc:** phân trang, lọc theo `status`, detail có `latest_job` và `speakers`. Response đúng schema của contract v0.
- **Xong khi:** test phân trang, lọc, 404; `contracts/openapi.json` không đổi (nếu đổi thì sinh lại cả `frontend/src/api/schema.d.ts`).
- **Message:** `feat(backend): meeting list and detail from the database (BE-05)`
- **Hash:**

### 11. [ ] `GET /meetings/{id}/transcript` và `GET /jobs/{id}` từ DB (BE-05)

- **Việc:** transcript chưa xong thì trả 200 với `status: "pending"` và `segments: []`, không trả 404.
- **Xong khi:** test transcript pending và ready (dùng dữ liệu seed), job các trạng thái.
- **Message:** `feat(backend): transcript and job status from the database (BE-05)`
- **Hash:**

### 12. [ ] `GET /meetings/{id}/audio` hỗ trợ HTTP Range (BE-05)

- **Việc:** trả 200 khi không có header Range, 206 với đúng đoạn byte khi có; file chỉ phục vụ qua endpoint có auth.
- **Xong khi:** test Range đầu, giữa, cuối file; Range sai thì 416; meeting của user khác thì 404.
- **Message:** `feat(backend): audio streaming with HTTP range support (BE-05)`
- **Hash:**

## Phần 4: worker và persist (BE-06, BE-07)

### 13. [ ] State machine của job, enqueue và claim (BE-06)

- **Việc:** `app/worker/queue.py`: claim job `queued` hoặc `retry_scheduled` đã tới `next_run_at`, dùng `SELECT … FOR UPDATE SKIP LOCKED`. Chuyển trạng thái sai (ví dụ `succeeded` → `running`) thì bị chặn.
- **Xong khi:** test 2 worker claim song song không bao giờ lấy trùng 1 job; các chuyển trạng thái sai bị chặn.
- **Message:** `feat(backend): job state machine and SKIP LOCKED claiming (BE-06)`
- **Hash:**

### 14. [ ] Worker loop chạy fake pipeline (BE-06)

- **Việc:** thêm `meeting-pipeline` làm dependency (path `../pipeline`). Worker ghi `job.json` vào `artifacts/{meeting_id}/{job_id}/`, gọi `run_job()` với `PIPELINE_BACKEND=fake`, cập nhật `stage` và `progress` (ghi DB tối đa 1 lần mỗi giây). Chỉ worker được import `meeting_pipeline`, và chỉ dùng `run_job`, `JobSpec`, `errors`.
- **Xong khi:** test: job `queued` chạy hết fake pipeline thành `succeeded`.
- **Message:** `feat(backend): worker loop running the pipeline through run_job (BE-06)`
- **Hash:**

### 15. [ ] Persist transcript, đợt 1 (BE-07)

- **Việc:** `on_stage_done(merge)`: validate `transcript.json` theo `contracts/pipeline/transcript.schema.json`, ghi `ai_outputs` (bất biến), `speakers` (`display_name` = "Speaker N"), `segments` (`ai_text` = `text`) trong 1 transaction, idempotent theo `(job_id, stage)`. `schema_version` không hỗ trợ thì job `failed` với `PIPELINE_OUTPUT_INVALID`.
- **Xong khi:** test persist 2 lần không tạo bản trùng (RT-12); fixture sai schema thì báo `PIPELINE_OUTPUT_INVALID`.
- **Message:** `feat(backend): persist transcript after merge, idempotent per job and stage (BE-07)`
- **Hash:**

### 16. [ ] Persist summary và action items, đợt 2 (BE-07)

- **Việc:** `on_stage_done(summarize)`: ghi summary và action items (`source=ai`, `ai_original`). Đổi `evidence_segment_indices` của pipeline sang `evidence_segment_ids`. `status=disabled` hoặc `insufficient_content` thì ghi đúng trạng thái.
- **Xong khi:** test với `contracts/fixtures/pipeline/summary*.json`, gồm cả evidence trỏ tới index không tồn tại (bỏ evidence đó và đặt `needs_review`).
- **Message:** `feat(backend): persist summary and action items with evidence ids (BE-07)`
- **Hash:**

## Phần 5: độ tin cậy (BE-08)

### 17. [ ] Lease, heartbeat và reaper (BE-08)

- **Việc:** lease 60 s, heartbeat 15 s; reaper chạy mỗi 30 s, đưa job hết lease về `queued` và tăng `attempt`. SIGTERM thì trả lease, không tăng `attempt`. Clock thay được trong test.
- **Xong khi:** test RT-08 (worker chết giữa chừng thì job được requeue) và RT-09 (SIGTERM) với clock giả.
- **Message:** `feat(backend): job lease, heartbeat and reaper (BE-08)`
- **Hash:**

### 18. [ ] Chính sách retry (BE-08)

- **Việc:** lỗi permanent (`PermanentPipelineError`) thì `failed` ngay; lỗi transient hoặc timeout thì `retry_scheduled`, backoff 30 s → 2' → 8' ±20 %, tối đa 3 lượt; hết lượt thì `failed`. Ghi `error_code` và `error_message` (không chứa transcript).
- **Xong khi:** test RT-01, RT-03, RT-04, RT-05 bằng `FAKE_SCENARIO` (`timeout`, `summary_flaky`, `permanent`…).
- **Message:** `feat(backend): retry policy with backoff for transient pipeline errors (BE-08)`
- **Hash:**

### 19. [ ] Lỗi một phần: diarize fallback và summary lỗi (BE-08, BE-10)

- **Việc:** diarize fallback thì meeting `ready` kèm warning `DIARIZATION_FALLBACK`; summarize lỗi permanent thì meeting `partial`, transcript vẫn đọc được.
- **Xong khi:** test RT-02 và RT-04 với `FAKE_SCENARIO=diarize_fail` và `summary_fail`.
- **Message:** `feat(backend): partial results for diarization fallback and failed summaries (BE-08)`
- **Hash:**

## Phần 6: test tích hợp M1

### 20. [ ] Luồng M1 từ upload tới transcript (M1)

- **Việc:** `tests/integration/test_m1_flow.py`: đăng nhập, upload một file wav sinh lúc chạy test, worker chạy fake pipeline, `GET /jobs/{id}` ra `succeeded`, `GET /transcript` trả đúng fixture. Cập nhật `backend/README.md` (cách chạy API và worker).
- **Xong khi:** test xanh trên CI có Postgres.
- **Message:** `test(backend): M1 flow from upload to transcript with the fake pipeline (M1)`
- **Hash:**

## Việc chung (không phải commit)

- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash. Làm không hết 20 commit thì ghi rõ commit nào chuyển sang ngày sau.
- [ ] Push `haquang`, mở PR vào `main`, tiêu đề theo format commit. **Không tự merge.** Nếu đổi `contracts/openapi.json` thì commit cả `frontend/src/api/schema.d.ts`.
