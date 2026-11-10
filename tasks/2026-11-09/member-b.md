# 2026-11-09 · Member B: profile upload, nhiều worker API, tách controller, smoke test (Đợt 4)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #41 và #42 đã vào `main`.
- **Mục tiêu:** 247 client đã hết lỗi (C sửa hôm nay) nhưng p95 chỉ-upload còn 2,2 đến 2,4 s ở 4 process và 4,1 s ở 1 process, trên mốc 2,0 s. Giảm phần còn lại bằng số đo, tiếp tục tách `meetings.py`, thêm smoke test end-to-end trên Compose.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 4. Kiểm tra trong `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Máy có `ffprobe` thật thì 5 test upload lỗi `AUDIO_INVALID` từ trước (CI xanh).

## Việc đầu tiên (không tính commit): review PR của C
C mở PR `tainguyen` hôm nay (chẩn đoán 61 s, giới hạn request đang xử lý, metric quá tải, đồng bộ hạn lưu trữ, bản đồ evidence). **Ghi nhận xét thật vào PR** (PR #40 hôm qua vào `main` mà không có review ghi lại; không lặp lại). Kiểm riêng: con số trong `docs/evidence/` có khớp `raw.csv`, có ghi giới hạn phép đo không.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [x] Tìm và giảm thời gian xử lý của một upload (AD-018, BE-12)
- Nguyên nhân 61 s đã được C tìm ra và sửa (`docs/evidence/load-247/diagnosis.md`, `app/core/admission.py`); `ffprobe` chỉ ~15 ms nên **không** phải thủ phạm. Còn lại: với 4 process, p95 **chỉ-upload** vẫn 2,2 đến 2,4 s (`docs/evidence/load-247/after/README.md`). Lấy profile `POST /meetings` ở 40 request đồng thời (cProfile hoặc py-spy, ghi cách chạy), tìm điểm nóng thật (parse multipart, sha256, ghi file, các lần commit) rồi giảm.
- Profile cProfile phát hiện điểm nóng: Session expire sau commit đầu tiên gây ra 4 truy vấn dư thừa (reload User, reload IdempotencyKey qua select, reload Job và Meeting sau commit cho log). Tối ưu hóa: lưu `current_user_id` trước commit, cập nhật IdempotencyKey trực tiếp qua lệnh `UPDATE` thay vì `SELECT + flush`, dùng biến cục bộ `job_id`/`meeting_id` trong log, bỏ `flush` trung gian.
- Kết quả: Giảm từ 10 truy vấn SQL xuống còn đúng 6 truy vấn mỗi upload (~40% số query).
- Test đỏ trước: `test_upload_meeting_query_count_budget` trong `tests/api/test_upload_meeting.py` (fail ở 9 queries, pass ở 6 queries).
- **Commit:** `ecdcee5`
- **Message:** `perf(backend): eliminate redundant queries and post-commit lazy loads in upload (AD-018)`

### 2. [x] `API_WORKERS`: chạy nhiều process uvicorn trong image (AD-018, BE-16)
- Biến môi trường `API_WORKERS` (mặc định 1) điều khiển số process Uvicorn trong image API (`api.Dockerfile`) và `docker-compose.yml`.
- Kiểm tra khởi động (startup check): bắt buộc tổng kết nối `API_WORKERS * API_MAX_INFLIGHT < POSTGRES_MAX_CONNECTIONS` (100) để tránh cạn kiệt connection pool của PostgreSQL trong Compose (ví dụ: 4 worker x 20 inflight = 80 < 100 đạt; 4 x 40 = 160 >= 100 ném ValueError).
- Ghi tài liệu chi tiết công thức tính kết nối DB trong `infra/docker/README.md` và `.env.example`.
- Bộ 6 test kiểm tra các mốc tại `backend/tests/unit/test_api_workers_config.py`.
- **Commit:** `32bfa60`
- **Message:** `feat(infra): API_WORKERS controls uvicorn processes, documented with connection math (AD-018)`

### 3. [x] Tách tiếp `meetings.py` (hiện 1216 dòng) (BE-12)
- Tách `GET /{meeting_id}/audio` và helper `stream_file_range` sang `backend/app/api/v1/audio.py`.
- Tách `GET /{meeting_id}/transcript` sang `backend/app/api/v1/transcript.py`.
- Giảm số dòng `meetings.py`: từ 1216 dòng xuống 946 dòng (giảm 270 dòng).
- Giữ nguyên thứ tự đăng ký router, 0 drift OpenAPI (`test_openapi_drift.py` 46 passed).
- **Commit:** `2db0f3f`
- **Message:** `refactor(backend): move audio and transcript routes out of meetings.py (BE-12)`

### 4. [x] `make smoke`: Compose lên thật, đi hết một job với pipeline giả (BE-16, BE-15)
- Tạo script `backend/scripts/smoke_compose.py`: chờ API ready, tạo user tổng hợp, đăng nhập, upload WAV tổng hợp, poll job tới `succeeded` với fake pipeline, tải export các định dạng (txt, json, md), và dọn dẹp sạch meeting + user tổng hợp.
- Bổ sung target `smoke` vào `Makefile` (`make smoke`) và cập nhật `README.md`.
- Thêm job `compose-smoke` vào workflow `.github/workflows/docker-images.yml` để chạy kiểm thử khói tự động trên CI.
- **Commit:** `d9b12e5`
- **Message:** `test(infra): make smoke runs a job end to end on Compose (BE-16)`

### 5. [x] Tick, hash, cập nhật `docs/evidence/reliability.md` nếu có số mới (G0)
- Hoàn tất tick các việc và ghi nhận đầy đủ hash commit của ngày 2026-11-09.
- Hoàn thành review PR #43 của C tại `docs/backend/reviews/PR-43-2026-11-09.md` (đối chiếu số liệu thô khớp 100%, xác nhận giới hạn phép đo trung thực).
- **Commit:** `c3d7c87` (hoặc commit ghi nhận này)
- **Message:** `docs(tasks): record 2026-11-09 member B results (G0)`

## Gửi C khi xong commit 1–2
Ping vào PR để C đo lại 247 (3 lần, cả 1 và 4 process) trên nhánh của bạn; C ghi kết quả thật, kể cả khi vẫn không đạt.
