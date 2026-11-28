# 2026-11-28 · Member B: chạy lại khi không còn audio làm mất transcript trên giao diện, evidence của tóm tắt AI, mã lỗi của worker, warning cuối cùng (Đợt 18, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **đúng 5**. Nếu API đổi schema, chạy `npm run gen:api` và đưa `frontend/src/api/schema.d.ts` vào **cùng commit** đó.
- **Điều kiện bắt đầu:** #83 (A) và #84 (B) đã vào `main` (`03f16fb`, `af2dc6a`). C gộp hai PR với `main` rồi chạy trên PostgreSQL 16 nghe IPv4 và IPv6 trên Linux:
  - **575 passed, 0 skipped, 0 xfailed, 1 warning.** Ba test B bị skip trên Windows đều chạy và đạt.
  - E2E `missing-audio`, `upload`, `retention`, `evidence-seek`, `summary-edit` trên API thật: đạt.
- **Review #84 (C):** 4 việc đúng. PR có 6 commit (commit `011a946` sinh lại `schema.d.ts`, chưa ghi trong file tick). Hai lỗi P2 thành việc 1 và việc 2 hôm nay; lỗi ở việc 2 do C đặt giới hạn mà chưa kiểm đầu ra của AI.
- **Review chéo:** B chưa review #83 và A chưa review #84 khi C merge.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-28. Không phụ thuộc PR của A.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [ ] Chạy lại khi audio không còn làm cuộc họp `failed` và transcript biến mất (BE-10, BE-16)
- **Lỗi (C tái hiện ngày 11-28 trên PostgreSQL, có từ trước #84):** cuộc họp `ready`, audio đã hết hạn, `POST /meetings/{id}/jobs` với `from_stage: asr` được **202**. Worker đánh job `failed` (`AUDIO_EXPIRED`), cuộc họp thành `failed`, `GET /transcript` trả **danh sách rỗng**. Đoạn thoại vẫn còn trong DB nhưng người dùng không đọc được, và không chạy lại được nữa.
  - Đường này đi qua API; giao diện chỉ gọi `from_stage: summarize`, đường đó vẫn chạy đúng.
- **Test:** `backend/tests/integration/test_rerun_without_audio_postgres.py`:
  - `test_rerun_that_needs_audio_is_refused_and_the_transcript_stays` (2 ca) đánh `xfail(strict=True)`.
  - `test_summary_rerun_still_works_after_the_audio_expired` phải vẫn xanh.
- **Sửa:** trước khi tạo job, nếu stage bắt đầu cần audio (mọi trường hợp trừ `summarize`):
  - hết hạn lưu thì **410 `AUDIO_EXPIRED`**;
  - không tìm thấy file thì **404 `AUDIO_NOT_FOUND`**;
  - không tạo job, không đổi `meeting.status`, `Idempotency-Key` dùng lại được.
  - Khai 404 và 410 trong `responses` của route, cập nhật `contracts/openapi.json`.
- **Bỏ dấu xfail.**
- **Message:** `fix(backend): a rerun that needs audio is refused when the audio is expired or missing, keeping the meeting and transcript (BE-10, BE-16)`
- **Commit:** _chưa_

### 2. [ ] Persister lưu hơn 50 evidence mỗi ý nên tóm tắt AI không sửa được (BE-05, AI-09)
- **Lỗi:** từ #84, `PUT /summary` nhận tối đa 50 evidence mỗi ý. `app/worker/persister.py` lưu nguyên danh sách của `summary.json`. Ý có 51 evidence: `GET` trả 51, sửa tổng quan rồi `PUT` được **422**.
  - C đã sửa hậu kiểm pipeline (giữ 50, ngày 11-28). `summary.json` sinh trước đó hoặc từ provider khác vẫn có thể vượt.
- **Test:** `test_put_summary_that_keeps_the_evidence_of_an_ai_summary_answers_200` trong `test_field_limits_postgres.py`, đang `xfail(strict=True)`.
- **Sửa:** persister giữ tối đa 50 id khác nhau mỗi ý chính và quyết định, cho cả `content` và `ai_content`. `ai_outputs.payload` giữ nguyên bản gốc. Không cần migration.
- Trả lại `description` của `evidence_segment_ids` trong schema đầu vào (OpenAPI mất mô tả từ #84).
- **Bỏ dấu xfail.**
- **Message:** `fix(backend): the persister keeps at most 50 distinct evidence ids per summary point so a stored AI summary can be saved (BE-05, AI-09)`
- **Commit:** _chưa_

### 3. [ ] Worker báo mã và câu lỗi không khớp khi mất audio (BE-10; P3 của C trên #84)
- `runner.py`: job `AUDIO_EXPIRED` vẫn mang `error_message` "Không tìm thấy tệp âm thanh hợp lệ trong storage."; file mất khi còn hạn vẫn là `AUDIO_INVALID` ("File audio không hợp lệ hoặc không thể đọc").
- **Sửa:**
  - Mất file khi còn hạn: `AUDIO_NOT_FOUND`. `AUDIO_INVALID` chỉ dùng khi file có mà không đọc được.
  - `error_message` đi theo mã.
  - Luật "đã hết hạn lưu" (kể cả gắn múi giờ UTC) viết một chỗ, dùng chung cho `audio.py`, `runner.py` và việc 1.
- **Test:** hai ca mã và câu; sửa `test_worker_rejects_audio_outside_storage` theo mã mới.
- **Message:** `fix(backend): the worker reports AUDIO_NOT_FOUND for a missing file and a message that matches the code (BE-10, BE-16)`
- **Commit:** _chưa_

### 4. [ ] Warning cuối cùng khi chạy backend (BE-05)
- Starlette 1.9.0 báo `Using httpx with starlette.testclient is deprecated; install httpx2 instead`.
- `httpx2` trên PyPI là gói của Pydantic (`github.com/pydantic/httpx2`, C xem metadata ngày 11-28). Kiểm lại trước khi thêm.
- **Sửa:** thêm `httpx2` vào nhóm `dev` của `backend/pyproject.toml`, cập nhật `uv.lock`. Test và harness tải nào còn import `httpx` thì vẫn giữ `httpx`. Thêm `filterwarnings` để warning này thành lỗi.
- Nếu `httpx2` làm test đổi hành vi, không thêm; ghi lý do trong file này.
- Ghi số warning trước và sau.
- **Message:** `build(backend): TestClient runs on httpx2 and the deprecation warning fails the tests (BE-05)`
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy cả backend **trên Postgres**. Ghi số passed, **skipped, xfailed 0**, và số warning. Trên Windows, ghi tên từng test bị skip.
- Ruff check và format sạch.
- **Message:** `docs(tasks): record 2026-11-28 member B results (G0)`
- **Commit:** _chưa_

## Việc chung (không tính commit)

- Review PR ngày 11-28 của A **trong 18 giờ** kể từ lúc A mở, comment trên GitHub. #83 chưa có review của B.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.
