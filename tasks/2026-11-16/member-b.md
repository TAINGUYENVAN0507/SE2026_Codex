# 2026-11-16 · Member B: sửa #61 theo review (log uvicorn, smoke Compose), số liệu người nói (Đợt 10, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`. **Push lên chính #61**, không mở PR mới.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #61 (B, ngày 11-15) chưa merge.
  - A review lúc 13:39 UTC ngày 11-15, sau 4,4 giờ, nêu hai điểm.
  - C kiểm lại ngày 11-16 và xác nhận cả hai: [review của C](https://github.com/TAINGUYENVAN0507/SE2026_Codex/pull/61).
  - #60 (A) đã vào `main` (`544333d`).
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** push trong ngày 11-16, rồi trả lời từng điểm trong review của A trên #61. C merge khi CI xanh.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [ ] Access log của uvicorn ghi cả query string (AD-018, BE-19). P1 của A
- **Lỗi:**
  - C chạy `uvicorn app.main:create_app --factory` với log mặc định, như `docker-compose.yml:33` và `infra/docker/api.Dockerfile:65`, rồi gọi `GET /api/v1/meetings?q=CANARY_...`.
  - Kết quả 401, nhưng stdout có `"GET /api/v1/meetings?q=CANARY_... HTTP/1.1" 401`.
  - `TestClient` không đi qua uvicorn, nên `test_access_logs_carry_no_personal_data` không thấy dòng này. `q` là tìm theo tiêu đề cuộc họp (`meetings.py:138`), và A sẽ cho giao diện gửi `q` (việc 2 của A).
- **Test đỏ trước,** trong `backend/tests/privacy/`:
  - Chạy uvicorn thật bằng subprocess, với **đúng cờ** lấy từ `docker-compose.yml` và `api.Dockerfile` (đọc file, không chép tay).
  - Gọi `?q=<canary>` và upload có tiêu đề canary.
  - Stdout và stderr không được chứa canary.
  - Thêm một ca đối chứng không có cờ tắt log: canary phải có, để chứng minh test bắt được lỗi.
  - Log đỏ: `docs/evidence/final/uvicorn-access-log-red-2026-11-16.log`.
- **Sửa:**
  - Thêm `--no-access-log` vào cả hai lệnh. `app.access` (`backend/app/core/middleware.py`) đã ghi method, path không kèm query, status và request_id, nên không mất thông tin vận hành.
  - Nếu chọn cách khác, ví dụ filter bỏ query, ghi lý do.
  - Sửa docstring sai ở đầu `test_privacy_access_log.py`, và test `test_uvicorn_access_log_settings_documented_in_infra` (hiện assert **không** có `--no-access-log`).
  - Sửa dòng "Log access của uvicorn và app.access" trong `docs/evidence/ad-018/README.md`: từ đầu dự án tới commit này, query string nằm trong log của container `api`.
- **Message:** `fix(infra): uvicorn writes no access log with query strings (AD-018, BE-19)`

### 2. [ ] Smoke Compose báo thành công khi không đọc được log container (AD-018, BE-16). P2 của A
- **Lỗi:** `backend/scripts/smoke_compose.py:203-208`: `docker compose logs` trả mã khác 0, hoặc máy không có `docker`, thì script chỉ in `[CẢNH BÁO]` rồi đi tiếp tới "SMOKE TEST THÀNH CÔNG".
- **Test đỏ trước:** mock `subprocess.run` của lệnh logs trả 1, và mock ném `FileNotFoundError`. Cả hai phải làm smoke lỗi. A đã dựng cách mock này ở `docs/frontend/reviews/PR-61-2026-11-15-smoke-control.json`. Lưu log đỏ UTF-8.
- **Sửa:** lỗi thu log thì smoke lỗi. Muốn bỏ qua khi chạy cục bộ thì dùng cờ riêng, ví dụ `--skip-docker-logs`; khi đó smoke in rõ "chưa kiểm log container", không in là đã kiểm. CI không dùng cờ này.
- **Message:** `fix(infra): compose smoke fails when container logs cannot be read (AD-018, BE-16)`

### 3. [ ] Smoke Compose kiểm cả tìm kiếm có canary (AD-018, BE-19)
- Sau upload có tiêu đề canary: gọi `GET /api/v1/meetings?q=<tiêu đề canary>` đã đăng nhập. Kết quả phải tìm thấy đúng meeting đó (`total == 1`). Sau đó `docker compose logs api worker` không được chứa canary.
- Đây là kiểm đầu-cuối của việc 1 trên image thật, chạy ở job `compose-smoke` của CI. Ghi link run vào file task.
- **Message:** `test(infra): compose smoke searches by the canary title and checks container logs (AD-018, BE-19)`

### 4. [ ] Số đoạn và thời gian nói của người nói luôn bằng 0 (BE-05)
- **Lỗi:**
  - `GET /meetings/{id}/transcript` (`transcript.py:82-83` trên head #61) và `GET /meetings/{id}` (`meetings.py:260-261`) trả `segment_count: 0`, `speaking_time_sec: 0.0` cho mọi người nói.
  - Trong khi đó `PATCH /speakers/{id}` (`speakers.py:55-70`) tính số thật, và fixture hợp đồng `contracts/fixtures/api/transcript_ready.json:12-13` có `1` và `6.42`. Ba nơi trả ba kiểu.
- **Test đỏ trước:** meeting `ready` có 3 segment của người nói 1 và 1 segment của người nói 2. Ở cả hai endpoint, `segment_count` và `speaking_time_sec` (tổng `end_sec - start_sec`, làm tròn như `speakers.py:56`) phải đúng, và bằng giá trị `PATCH /speakers/{id}` trả. Log đỏ UTF-8: `docs/evidence/final/speaker-stats-red-2026-11-16.log`.
- **Sửa:**
  - Transcript đã nạp segments, nên chỉ cần đếm.
  - Meeting detail dùng **một** truy vấn gộp theo `speaker_id`, không truy vấn từng người nói. `test_get_meeting_detail_query_budget_and_no_n_plus_one` (`backend/tests/api/test_poll_query_budget.py:176`) phải vẫn xanh.
  - Kiểm `openapi.json` không drift.
- **Message:** `fix(backend): speaker segment count and speaking time in transcript and meeting detail (BE-05)`

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy cả backend: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`. Ghi số test.
- **Message:** `docs(tasks): record 2026-11-16 member B results (G0)`

## Việc chung (không tính commit)

- Trả lời review của A trên #61: mỗi điểm ghi commit sửa và cách kiểm.
- Review PR ngày 11-16 của A trong 18 giờ kể từ lúc A mở. PR #60 của A (11-15) không có review của B sau 20 giờ.
