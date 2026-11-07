# 2026-11-06 · Member B: backend

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Mục tiêu:**
  - export thật;
  - xóa dữ liệu cá nhân khỏi mọi nơi lưu;
  - retention chạy thật;
  - log và metric đủ để lần ra nguyên nhân một job lỗi.

Kế hoạch các đợt sau: [`tasks/ROADMAP.md`](../ROADMAP.md).

Đọc trước:
- Mục BE-05, BE-14 và 10.4 (RT-13, PRIV-10, PRIV-12, PRIV-13, PRIV-14) của kế hoạch.
- `rules/privacy-security.md`.
- `backend/app/services/export/README.md`.

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

## Tránh đụng việc của C hôm nay

C đang sửa trên nhánh `tainguyen-vt018` các phần sau. Bạn không sửa chúng hôm nay để tránh conflict:
- `app/worker/persister.py`;
- `handle_progress` trong `app/worker/runner.py`;
- `claim_job`, `complete_job`, `fail_job` trong `app/worker/queue.py`;
- `serialize_job` trong `meetings.py`, `get_job` trong `jobs.py`.

C thêm migration `0006`, `0007`. **Hôm nay không cần migration nào của bạn.** Nếu buộc phải có, báo C trước để tránh hai head.

Không thêm logic mới vào `meetings.py` (2412 dòng, 18 route). Logic mới đặt trong `app/services/`, router chỉ gọi service.

## 5 commit

### 1. [x] Export dựng từ DB (BE-05, FE-15)

Chuyển từ 2026-10-29. PR #29 đã vào `main` nên không còn bị chặn.

- **Việc:** thay stub `export_meeting` (`meetings.py:2376`). Hiện hàm này trả chuỗi cố định, không kiểm owner, và có nhánh giả `"not-ready" in meeting_id`.
  - Thêm `app/services/meeting_export.py` dựng `MeetingExport` từ DB, cả 2 biến thể. Module `services/export/` không được query DB (`structure/architecture.md`).
  - Truyền đủ `evidence_segment_ids`, `needs_review` của action item, vì A in chúng ra file (FE-18).
  - Meeting của người khác: 404. Chưa có transcript: 409 `TRANSCRIPT_NOT_READY`. Định dạng lạ: 422 `FORMAT_NOT_SUPPORTED`.
  - Bỏ `docx` khỏi danh sách cho phép vì không có serializer. Sinh lại `contracts/openapi.json` nếu mô tả đổi.
- **Xong khi:** API test 3 định dạng × 2 biến thể; RT-13: gọi 3 lần cùng tham số ra cùng byte và không ghi gì vào DB; PRIV-12.
- **Message:** `feat(backend): export built from the database for both variants (BE-05, FE-15)`
- **Hash:** 3c1036e

### 2. [x] Service xóa dữ liệu, gồm cả `idempotency_keys` (BE-18)

Lỗi đã tái hiện: sau khi xóa meeting, `idempotency_keys.response_body` vẫn còn tiêu đề cuộc họp. Bảng này chỉ có FK tới `users`, nên không bị cascade, và replay cùng key sẽ trả lại dữ liệu đã xóa.

- **Việc:**
  - Thêm `app/services/erasure/`, chuyển logic của `delete_meeting` (`meetings.py:623`) vào đây. Router chỉ gọi service.
  - Xóa các dòng `idempotency_keys` của owner có `response_body` hoặc `endpoint` chứa `meeting_id`. Lọc bằng Python, không cần đổi schema.
  - Không để lại thư mục rỗng `artifacts/{meeting_id}/` khi worker dừng job bị hủy.
  - Log chỉ ghi id. Không ghi tiêu đề, tên file, nội dung.
- **Xong khi:**
  - test canary: tiêu đề và transcript chứa `CANARY_PERSONAL_7f3a`, sau khi xóa thì chuỗi này không còn trong **mọi bảng** (duyệt `Base.metadata`), cây `appdata/` và log đã capture;
  - test replay: gửi lại cùng `Idempotency-Key` sau khi xóa thì tạo meeting mới, không trả dữ liệu cũ.
- **Message:** `feat(backend): erasure service removes a meeting from every store (BE-18)`
- **Hash:** 9caad85

### 3. [x] Retention chạy thật (BE-14, PRIV-14)

Hiện `AUDIO_RETENTION_DAYS=30` trong `.env.example` không có tác dụng: `Settings` không có field này, `meetings.py:284` hard-code 30 ngày, và không có gì xóa file hết hạn.

- **Việc:**
  - `Settings`: `AUDIO_RETENTION_DAYS` mặc định 14, `OPERATIONAL_RETENTION_DAYS` mặc định 28. Cập nhật `.env.example`. Quy ước ở `tasks/ROADMAP.md`, mục Tham số.
  - Lệnh `python -m app.scripts.cleanup [--dry-run]`, và worker loop gọi mỗi giờ theo kiểu reaper.
  - Hết hạn audio: xóa audio và artifact, `audio.available=false`, `GET /audio` trả 410. Thêm mã lỗi `AUDIO_EXPIRED` vào `contracts/error_codes.md`. Transcript trong DB giữ tới khi người dùng xóa.
  - Hết hạn dữ liệu vận hành: xóa `idempotency_keys` quá hạn.
  - Bỏ qua meeting đang có job active. Dùng clock giả, không dùng giờ hệ thống trong test.
- **Xong khi:**
  - test biên: đúng lúc `retention_until` thì chưa xóa, sau 1 s thì xóa;
  - `--dry-run` không đổi gì;
  - PRIV-14 pass;
  - có `docs/privacy/data-policy.md`: dữ liệu gì, ở đâu, giữ bao lâu, xóa thế nào, gửi gì ra bên thứ ba, log giữ ra sao.
- **Message:** `feat(backend): retention cleanup removes expired audio and operational data (BE-14)`
- **Hash:** 3c00eb5

### 4. [x] Log JSON có job id, stage, attempt (BE-19)

Hiện `setup_logging()` không được gọi ở đâu cả, chỉ có test dùng formatter. Worker dùng `logging.basicConfig` (`runner.py:573`). Formatter chỉ giữ 4 field (`logging.py:30`), mọi `extra` khác bị bỏ.

- **Việc:**
  - Gọi `setup_logging()` khi khởi động API và worker.
  - Formatter giữ thêm các field chung trong `tasks/ROADMAP.md`, mục Field log. C dùng đúng các tên này ở pipeline (AI-18).
  - API ghi `job_created` kèm `job_id`, `meeting_id`, `request_id` ở `create_meeting` và `retry_meeting_job`. Không cần cột mới: dòng này nối request với job.
  - Worker ghi `job_claimed`, `job_retry_scheduled`, `job_failed`, `job_succeeded`, `job_lease_lost` kèm `job_id`, `stage`, `attempt`, `error_code`, `worker_id`.
- **Xong khi:** test `test_obs_failed_job_traceable`:
  - chạy fake `permanent`, lọc log theo `job_id`, thấy chuỗi từ `job_created` tới `job_failed` có `error_code` và `stage`;
  - chuỗi canary không có trong log (PRIV-10).
- **Message:** `feat(worker): JSON logs that carry job id, stage and attempt (BE-19)`
- **Hash:** 43515e3

### 5. [x] Endpoint `/metrics` (BE-19)

- **Việc:**
  - Thêm `prometheus-client`, chạy `uv lock`. Endpoint đặt ngoài `/api/v1`, `include_in_schema=False`. Compose ở đợt sau sẽ không proxy endpoint này ra ngoài.
  - API: `http_requests_total{method,route,status}`, `http_request_duration_seconds{route}`. Nhãn `route` là template, **không** phải đường dẫn thật, vì đường dẫn chứa id.
  - Job: worker và API là 2 process, nên đọc từ DB lúc scrape: số job theo `status`, tuổi job `queued` lâu nhất, số job lỗi theo `error_code` và `stage`.
  - Viết `docs/backend/BE-19.md`: từ một `job_id` lỗi, các bước tìm ra stage và mã lỗi; ghi thời gian đo thật khi làm thử.
- **Xong khi:** test parse được output; không có UUID trong output; số liệu job khớp DB.
- **Message:** `feat(backend): /metrics endpoint for requests, jobs and queue depth (BE-19)`
- **Hash:** cc4d453

## Việc chung (không phải commit)

- [ ] **Review PR `tainguyen-vt018` của C trong vòng 18 giờ từ lúc mở.** PR này sửa `app/worker/` và migration của bạn, và không được merge khi chưa có review của bạn. Ghi nhận xét thật trong PR.
- [ ] SH-01: ghi âm buổi họp pilot có consent (vẫn chưa có).

## Cuối ngày

- [x] Tick các ô ở trên và ghi hash.
- [x] Push `haquang`, mở PR vào `main`. **Không tự merge.**
