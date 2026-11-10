# 2026-11-10 · Member B: metric khi chạy nhiều process, controller nhỏ lại có test giữ, diễn tập runbook (Đợt 5)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 10, **cộng việc review**.
- **Điều kiện bắt đầu:** #44 và #45 đã vào `main` (2026-11-10).
- **Hạn:** mở PR trước tối 11-11. Ngày 11-12 đóng băng code, xem [`tasks/ROADMAP.md`](../ROADMAP.md).
- **Mục tiêu:** đóng các điểm còn mở trong review #45 của C. `/metrics` phải đúng khi `API_WORKERS > 1`. `meetings.py` (946 dòng) nhỏ lại, có test giữ không cho phình lại (AD-018: tách controller lớn). Runbook có thời gian truy nguyên nhân đo thật (RE-018).

Kiểm tra trong `backend/`: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Sau commit 1 của C hôm nay, 5 test upload không còn đỏ khi máy có ffprobe.

## Review (không bắt buộc, không tính commit)
Từ 2026-11-10, nhóm trưởng quyết định PR không cần chờ review của thành viên khác. Nhóm trưởng tự review diff, chờ CI xanh rồi merge. Nhận xét của bạn vẫn có ích nhưng không chặn merge. PR của C hôm nay là #46.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

## 10 commit

### 1. [ ] `/metrics` gộp đủ mọi process khi `API_WORKERS > 1` (RE-018, BE-19)
- Bật multiprocess mode của `prometheus_client` (`PROMETHEUS_MULTIPROC_DIR`, `MultiProcessCollector`). Gauge `api_inflight_requests` dùng `multiprocess_mode="livesum"`. Dọn thư mục khi khởi động.
- Test **đỏ trước**: chạy 2 process, gửi N request, rồi đọc `/metrics` vài lần; tổng `http_requests_total` phải bằng N ở mọi lần đọc.
- Sửa ghi chú "chưa gộp" trong `docs/backend/BE-19.md` và `docs/evidence/README.md`.
- **Message:** `feat(backend): /metrics adds up every API process when API_WORKERS > 1 (RE-018, BE-19)`

### 2. [ ] Phép tính kết nối chừa chỗ cho worker và migration (AD-018, BE-16)
- Review #45, điểm 1 và 2: dùng `API_WORKERS × API_MAX_INFLIGHT + DB_RESERVED_CONNECTIONS ≤ POSTGRES_MAX_CONNECTIONS`. Mặc định reserve đủ cho worker (đếm thật số kết nối worker mở) và migration. Đọc thêm `WEB_CONCURRENCY` hoặc ghi rõ trong README rằng chạy thẳng `uvicorn --workers` sẽ bỏ qua check.
- Test ở biên: vừa đủ thì qua, vượt 1 thì báo lỗi.
- **Message:** `fix(infra): connection budget reserves room for the worker and migrations (AD-018)`

### 3. [ ] Logic upload ra khỏi controller (AD-018, BE-12)
- `create_meeting` trong `meetings.py` (khoảng 240 dòng) chuyển phần nghiệp vụ (lưu file, probe, tạo meeting + job, idempotency) sang `app/services/meetings/upload.py`. Route chỉ còn đọc request, gọi service, trả response.
- Không đổi hành vi: test drift OpenAPI xanh, test upload và RT-07 xanh, query budget vẫn ≤ 6.
- **Message:** `refactor(backend): upload logic moves from the route into a service (AD-018, BE-12)`

### 4. [ ] Tách route speaker và lịch sử chỉnh sửa (BE-12)
- `PATCH /meetings/{id}/speakers/...` và `GET /meetings/{id}/edits` sang module riêng. Mục tiêu `meetings.py` dưới 500 dòng.
- **Message:** `refactor(backend): move speaker and edit-history routes out of meetings.py (BE-12)`

### 5. [ ] Một `serialize_job` duy nhất (BE-12)
- `jobs.py:44` có `serialize_job`, nhưng `serialize_meeting_detail` trong `meetings.py` (khoảng dòng 466) vẫn tự dựng `JobOut` cho job mới nhất. Gom về `serialize_job`. Test đối chiếu `job` trong `GET /meetings/{id}` với `GET /jobs/{id}` trên cùng job.
- **Message:** `refactor(backend): one job serializer for both routes (BE-12)`

### 6. [ ] Test giữ cho controller không phình lại (AD-018)
- Test kiến trúc: mọi file trong `app/api/v1/` không quá 500 dòng; route module không import `app.worker`. **Đỏ trước** khi chạy trên `main` hiện tại: có hai file vượt, `meetings.py` 946 dòng và `action_items.py` 558 dòng. Xanh sau commit 3–5, cộng phần tách `action_items.py` (ví dụ đưa serializer và kiểm tra evidence ra service). Ghi vào `docs/adr/` hoặc `docs/backend/` lý do chọn 500.
- **Message:** `test(backend): route modules stay under 500 lines and never import the worker (AD-018)`

### 7. [ ] Smoke dễ đọc khi fail (BE-16)
- Review #45, điểm 5: `smoke_compose.py` dùng kiểm tra tường minh thay cho `assert`. Job `compose-smoke` in `docker compose logs api worker` khi fail. Thử cho một bước fail trên nhánh tạm, dán link run vào thân commit.
- **Message:** `fix(infra): smoke checks survive python -O and print logs on failure (BE-16)`

### 8. [ ] Log trên Compose có giới hạn, tài liệu nói đúng (AD-018)
- `docker-compose.yml`: logging `json-file` có `max-size`/`max-file` cho `api`, `worker`. Trong `docs/privacy/data-policy.md`, ghi đúng cách log được giữ: Docker xoay vòng log theo dung lượng, không theo ngày. `OPERATIONAL_RETENTION_DAYS=28` áp dụng cho `idempotency_keys`; log không chứa nội dung cuộc họp (test canary). Không được ghi là log tự xóa sau 28 ngày nếu cấu hình không làm vậy.
- **Message:** `feat(infra): bounded container logs, retention doc says what really happens (AD-018)`

### 9. [ ] Diễn tập runbook: hai sự cố, đo thời gian tìm ra nguyên nhân (RE-018, BE-19)
- Trên Compose, tạo 2 sự cố: (a) giết worker giữa lúc job đang chạy, (b) dừng `db` trong 30 s. Với mỗi sự cố, chỉ dùng log JSON và `/metrics` theo runbook, ghi lại: lúc tạo lỗi, lúc phát hiện, lúc biết nguyên nhân, lệnh đã chạy, log khớp `job_id`. Kết quả vào `docs/backend/runbook-drill-2026-11-10.md`. Runbook thiếu bước nào thì bổ sung.
- **Message:** `docs(backend): runbook drill with two injected failures and measured time to cause (RE-018)`

### 10. [ ] Tick, hash, bằng chứng profile (G0)
- Commit file profile `POST /meetings` (đầu ra cProfile hoặc py-spy và cách chạy) vào `docs/evidence/load-247/profile/`. PR #45 nói đã profile nhưng chưa có file nào trong repo. Ghi số query trước khi sửa đúng như đo được (9 hay 10).
- Ghi hash từng commit vào file này. Việc chưa xong thì ghi "chuyển sang 11-11", không tick.
- **Message:** `docs(tasks): record 2026-11-10 member B results and upload profile (G0)`
