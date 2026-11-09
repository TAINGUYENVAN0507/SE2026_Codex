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

### 1. [ ] Tìm và giảm thời gian xử lý của một upload (AD-018, BE-12)
- Nguyên nhân 61 s đã được C tìm ra và sửa (`docs/evidence/load-247/diagnosis.md`, `app/core/admission.py`); `ffprobe` chỉ ~15 ms nên **không** phải thủ phạm. Còn lại: với 4 process, p95 **chỉ-upload** vẫn 2,2 đến 2,4 s (`docs/evidence/load-247/after/README.md`). Lấy profile `POST /meetings` ở 40 request đồng thời (cProfile hoặc py-spy, ghi cách chạy), tìm điểm nóng thật (parse multipart, sha256, ghi file, các lần commit) rồi giảm.
- Test **đỏ trước** cho điểm nóng bạn sửa (ví dụ đếm số commit hoặc số query của một upload); ghi tên test đỏ trong thân commit. Không đổi hành vi hay contract. Nếu profile cho thấy không có gì đáng sửa trong mã, ghi đúng như vậy và đổi việc này sang tách `meetings.py`.
- **Message:** `perf(backend): <điểm nóng thật tìm được từ profile> (AD-018)`

### 2. [ ] `API_WORKERS`: chạy nhiều process uvicorn trong image (AD-018, BE-16)
- Biến môi trường đặt số worker (mặc định 1), ghi vào `infra/docker/README.md`. **Tính kết nối theo `API_MAX_INFLIGHT`** (mỗi process), không theo pool: tổng = số worker × `API_MAX_INFLIGHT` phải nhỏ hơn `max_connections` của Postgres trong Compose (đo hôm nay: 4 worker, `API_MAX_INFLIGHT=20`, 80 < 100). Thêm kiểm tra khởi động hoặc test cho phép tính này.
- **Message:** `feat(infra): API_WORKERS controls uvicorn processes, documented with connection math (AD-018)`

### 3. [ ] Tách tiếp `meetings.py` (hiện 1216 dòng) (BE-12)
- Chuyển nhóm route audio/transcript hoặc nhóm speaker sang module riêng, không đổi hành vi, `test_openapi_drift.py` không đổi. Ghi số dòng trước/sau.
- **Message:** `refactor(backend): move audio and transcript routes out of meetings.py (BE-12)`

### 4. [ ] `make smoke`: Compose lên thật, đi hết một job với pipeline giả (BE-16, BE-15)
- Đăng ký user tổng hợp, upload WAV tổng hợp, poll tới `succeeded`, tải export, xóa. Dùng chung với CI nếu được (dán link run). Không dữ liệu thật.
- **Message:** `test(infra): make smoke runs a job end to end on Compose (BE-16)`

### 5. [ ] Tick, hash, cập nhật `docs/evidence/reliability.md` nếu có số mới (G0)
- Ghi hash vào file này. Không sửa số đo tải: C đo lại.
- **Message:** `docs(tasks): record 2026-11-09 member B results (G0)`

## Gửi C khi xong commit 1–2
Ping vào PR để C đo lại 247 (3 lần, cả 1 và 4 process) trên nhánh của bạn; C ghi kết quả thật, kể cả khi vẫn không đạt.
