# 2026-11-07 · Member B: xóa tài khoản, metric theo stage, đóng gói

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **cộng việc review**.
- **Điều kiện bắt đầu:** PR #33 và #34 đã vào `main`.
- **Mục tiêu:** xóa được toàn bộ dữ liệu của một người dùng; metric thời lượng từng stage; `meetings.py` nhỏ hơn; chạy được bằng Compose.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 2. Lệnh kiểm tra, trong `backend/` (cần Postgres): `uv run ruff check . && uv run ruff format --check . && uv run pytest`.

## Việc đầu tiên (không tính commit): review PR #35
PR `tainguyen-vt018` của C sửa `persister.py`, `runner.py`, `queue.py` và thêm migration 0006, 0007. **VT-018 cấm merge khi nhóm chưa review**. Đọc diff, ghi nhận xét thật trong PR (đừng chỉ bấm approve), nêu ít nhất: migration 0006 xóa dòng trùng có chấp nhận được không; có chỗ nào ghi `progress` mà bỏ qua `max(...)`. Hạn: 18 giờ từ lúc mở (2026-11-06).

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```
Tránh đụng: file của PR #35 cho tới khi nó merge.

## 5 commit

### 1. [ ] `DELETE /auth/me` xóa toàn bộ dữ liệu người dùng (BE-18)
- Dùng lại `app/services/erasure/`: xóa mọi meeting, file, `idempotency_keys`, cuối cùng là user; cookie phiên bị xóa. Sinh lại `contracts/openapi.json` và `frontend/src/api/schema.d.ts`.
- **Xong khi:** canary `CANARY_PERSONAL_7f3a` không còn trong mọi bảng, `appdata/` và log; user khác không bị ảnh hưởng (PRIV-12); gọi lần 2 trả 401.
- **Message:** `feat(backend): delete the account and everything it owns (BE-18)`
- **Hash:**

### 2. [ ] Thời lượng từng stage trong metric (BE-19)
- Worker lưu `outcome.timings` (hiện bị bỏ ở `runner.py`); `/metrics` có `pipeline_stage_duration_seconds{stage}`. Nhãn chỉ là tên stage.
- **Xong khi:** test parse output; không có UUID; cập nhật `docs/backend/BE-19.md` mục chẩn đoán stage chậm.
- **Message:** `feat(worker): per-stage duration metric from the pipeline timings (BE-19)`
- **Hash:**

### 3. [ ] Tách route action item khỏi `meetings.py`
- Chuyển nguyên route action item sang `app/api/v1/action_items.py`, **không đổi hành vi**. Sửa `config.py:34` còn liệt kê `docx`.
- **Xong khi:** `contracts/openapi.json` không đổi (test drift), toàn bộ test cũ xanh, `meetings.py` giảm đúng số dòng đã chuyển.
- **Message:** `refactor(backend): move action item routes out of meetings.py (BE-12)`
- **Hash:**

### 4. [ ] Dockerfile cho API và web (BE-16)
- Dockerfile cho API (kèm worker) và web (nginx phục vụ build). Không chứa secret; chạy user không phải root.
- **Xong khi:** CI build được cả hai ảnh; ghi kích thước ảnh.
- **Message:** `feat(infra): Dockerfiles for the API and web (BE-16)`
- **Hash:**

### 5. [ ] Compose đủ bốn service có healthcheck (BE-16)
- `db`, `api`, `worker`, `web`, healthcheck, `depends_on: condition: service_healthy`. `/metrics` không được proxy ra ngoài qua nginx.
- **Xong khi:** `docker compose up` cho smoke test upload → transcript chạy qua; ghi lệnh vào README.
- **Message:** `feat(infra): compose with db, api, worker and web (BE-16)`
- **Hash:**

## Cuối ngày
- [ ] Tick và ghi hash. Push `haquang`, mở PR vào `main`. **Không tự merge.**
