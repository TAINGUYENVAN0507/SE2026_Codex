# 2026-11-11 · Member B: metric của worker đọc được từ `/metrics`, metric nhiều process không giữ số cũ (Đợt 6)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #47 và #48 đã vào `main` (C merge ngày 2026-11-11, `1f9d1ca`). Không còn việc chuyển từ 11-10: cả 10 ô đã tick.
- **Hạn:** mở PR trong ngày 11-11. Ngày 11-12 **đóng băng code**, chỉ còn sửa lỗi.
- **Mục tiêu:** khi C review #48, đã ghi ba điểm sau. Cần đóng chúng trước khi đóng băng code.
  1. Worker ghi `pipeline_stage_duration_seconds` (`backend/app/worker/runner.py:394`) trong process riêng. API không đọc được: trên Compose, `api` và `worker` là hai container, mỗi bên có `/tmp/prometheus_multiproc_dir` riêng. Ở cấu hình 1 process trước #48 cũng vậy. Bảng RE-018 đang ghi "Thời lượng từng stage trong metric ✓", nhưng thực tế không scrape được số đó.
  2. Ở chế độ nhiều process, `collect_db_metrics` bỏ `JOBS_FAILED_TOTAL.clear()`. Nhóm `(stage, error_code)` nào hết job failed (ví dụ job được retry thành công rồi bị xóa) thì vẫn giữ số cũ, không về 0.
  3. Gauge `livesum` không gọi `multiprocess.mark_process_dead`. Khi một process uvicorn chết và được thay, file của process cũ vẫn được cộng vào `api_inflight_requests`.

Kiểm tra trong `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Kết quả của C khi gộp thử #47 và #48: 393 passed, 14 skipped.

## Review (không bắt buộc, không tính commit)
Nhóm trưởng tự review diff, chờ CI xanh rồi merge.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [ ] Thời lượng stage của worker hiện trên `/metrics` của API (RE-018, BE-19)
- Trên Compose, `api` và `worker` mount chung một volume vào `PROMETHEUS_MULTIPROC_DIR`. Chỉ `api` dọn thư mục khi khởi động. Ghi trong `docs/backend/BE-19.md`: khi chạy dev không qua Compose, đặt cùng `PROMETHEUS_MULTIPROC_DIR` cho cả hai lệnh.
- Test **đỏ trước**: một subprocess đóng vai worker ghi `pipeline_stage_duration_seconds` vào thư mục chung. `GET /metrics` của API (cùng thư mục) phải có `_count` > 0 cho stage đó.
- `smoke_compose.py`: sau khi job xong, kiểm tra `pipeline_stage_duration_seconds_count` > 0 (đọc `/metrics` trong mạng nội bộ, không qua nginx).
- **Message:** `fix(infra): worker stage durations reach the API /metrics (RE-018, BE-19)`

### 2. [ ] Metric job theo DB không giữ nhóm đã hết (BE-19)
- Ở chế độ nhiều process, `jobs_failed_total` và `jobs_total` phản ánh đúng DB tại lúc scrape. Nhóm nào về 0 thì hiện 0 hoặc biến mất, không giữ số cũ.
- Test **đỏ trước**: tạo 1 job failed, scrape thấy 1; xóa job, scrape lại phải thấy 0 hoặc không còn dòng đó.
- **Message:** `fix(backend): DB-backed job gauges drop groups that reached zero (BE-19)`

### 3. [ ] Process API chết thì không còn bị cộng vào `api_inflight_requests` (BE-19)
- Gọi `multiprocess.mark_process_dead(pid)` khi process API tắt (lifespan shutdown). Nếu uvicorn không gọi được khi process bị kill, ghi giới hạn này trong `docs/backend/BE-19.md`, không ghi là đã xử lý.
- Test: tạo file gauge của một pid giả đã chết, gọi hàm dọn, rồi scrape không còn cộng số đó.
- **Message:** `fix(backend): a stopped API process no longer counts toward in-flight requests (BE-19)`

### 4. [ ] Query budget cho đường poll: `GET /jobs/{id}` và `GET /meetings/{id}` (AD-018, BE-12)
- Ở 247 client, mỗi client poll `GET /jobs/{id}` 5 lần. Đếm số query của hai route này như test budget của upload (≤ 6), đặt ngưỡng bằng số đo được. Nếu thấy N+1 (theo số segment hoặc speaker) thì sửa.
- Ghi số đo vào `docs/backend/AD-018.md`.
- **Message:** `test(backend): query budget for the job and meeting reads clients poll (AD-018)`

### 5. [ ] Tick, hash; README backend đúng với cấu hình mới (G0)
- Theo `README.md` và `backend/README.md` trên clone sạch, chạy migration, API, worker. Kiểm tra các biến mới của #48 (`DB_RESERVED_CONNECTIONS`, `WEB_CONCURRENCY`, `PROMETHEUS_MULTIPROC_DIR`) đều có trong README và `.env.example`, ghi đúng giá trị mặc định.
- Ghi hash từng commit vào file này. Việc chưa xong thì ghi "chuyển sang 11-12 (chỉ nếu là sửa lỗi)", không tick.
- **Message:** `docs(tasks): record 2026-11-11 member B results, backend README matches config (G0)`
