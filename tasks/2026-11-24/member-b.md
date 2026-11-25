# 2026-11-24 · Member B: preflight IPv6, N+1 ở danh sách, bốn trường trả 500 trên Postgres, đường dẫn dự phòng của worker (Đợt 14, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Chuyển từ 11-23:** B chưa mở PR và nhánh `haquang` chưa có commit mới, nên cả 5 việc ngày 11-23 đều chưa tick. Việc 1, 2 và 4 dưới đây chuyển từ `tasks/2026-11-23/member-b.md`. Việc 3 ngày 11-23 (test xóa cuộc họp theo `STORAGE_DIR`) để đợt sau, nhường chỗ cho việc 3 dưới đây vì việc này là lỗi 500 thật.
- **Điều kiện bắt đầu:** `main` tại `b35e06f` (sau #71 và #72).
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-24. Không phụ thuộc PR của A.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [x] Preflight Postgres trong `conftest.py` từ chối IPv6 (chuyển từ 11-23, việc 1; finding P2 của A trên #70)
- Như `tasks/2026-11-23/member-b.md`, việc 1. Test đỏ trước với URL `[::1]`, rồi sửa bằng `socket.create_connection` hoặc bỏ bước socket riêng.
- **Message:** `fix(backend): the test Postgres preflight accepts IPv6 hosts (BE-16, G0)`
- **Commit:** `91f5c23`

### 2. [x] N+1 ở `GET /meetings` (chuyển từ 11-23, việc 2)
- Như `tasks/2026-11-23/member-b.md`, việc 2:
  - Test ngân sách truy vấn đỏ trước, với 1 và 10 mục, có và không có `q`.
  - Lấy job mới nhất của mọi cuộc họp trong trang bằng một truy vấn.
  - Response giữ nguyên.
- **Message:** `fix(backend): the meeting list loads the latest job of every meeting in one query (BE-05, AD-018)`
- **Commit:** `cc0e33c`, `bde32b7` (tách serialization sang `app/services/meetings/queries.py` để controller dưới 500 dòng)

### 3. [x] Bốn trường trả 500 thay vì 4xx khi quá giới hạn trên PostgreSQL (BE-05, AD-018)
- **Lỗi (C tìm ngày 11-24, test `backend/tests/integration/test_field_limits_postgres.py`):** SQLite không kiểm độ dài `VARCHAR(n)`, nên các test cũ không thấy lỗi. Trên Postgres:
  - `POST /meetings`, `title` 201 ký tự: **500** `StringDataRightTruncation` (cột `String(200)`; `PATCH` đã chặn 200, `POST` thì không). C thử trên API thật: 200 ký tự trả 201, 201 ký tự trả 500, 1000 ký tự thì kết nối bị reset.
  - `POST /meetings`, `meeting_date` không đúng `YYYY-MM-DD` (13 ký tự): **500**. Cột `String(10)`, form không kiểm định dạng.
  - `POST /meetings`, header `Idempotency-Key` 101 ký tự: **500**. Cột `String(100)`.
  - `POST /meetings/{id}/action-items`, `due_date` không đúng `YYYY-MM-DD`: **500**. Cột `String(10)`.
- **Sửa:**
  - `title` 1 đến 200 ký tự sau khi strip, giống `PATCH`.
  - `meeting_date` và `due_date` phải là ngày `YYYY-MM-DD` hợp lệ, sai thì 422.
  - `Idempotency-Key` tối đa 100 ký tự, quá thì 400 hoặc 422 với mã lỗi riêng.
  - Cập nhật `contracts/openapi.json`.
- **Bỏ 4 dấu `XFAIL_B`** trong `test_field_limits_postgres.py`. Dấu này là `strict=True`, nên sau khi sửa các ca đó chuyển sang XPASS và làm suite đỏ nếu chưa bỏ. Chạy test này trên Postgres trước và sau khi sửa, log UTF-8 `docs/evidence/final/field-limits-postgres-2026-11-24.log`.
- **Message:** `fix(backend): over-long titles, idempotency keys and malformed dates answer 4xx instead of 500 on PostgreSQL (BE-05, AD-018)`
- **Commit:** `ec247e3`

### 4. [x] Worker dự phòng ghi artifact vào `./appdata` tương đối (chuyển từ 11-23, việc 4)
- Như `tasks/2026-11-23/member-b.md`, việc 4: dùng storage giả không có `base_dir`, artifact phải nằm trong `STORAGE_DIR`.
- **Message:** `fix(backend): the worker falls back to STORAGE_DIR, not a relative appdata folder, for artifacts (BE-16)`
- **Commit:** `70df44f`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này". Ghi "chuyển sang 11-24" vào các ô của `tasks/2026-11-23/member-b.md`.
- Chạy cả backend **trên Postgres**: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`. **Số skipped phải là 0, số xfailed phải là 0.**
- Kết quả test cục bộ trên PostgreSQL + `ffprobe` (Windows): `534 passed, 3 skipped, 0 failed, 0 xfailed` (3 skipped chỉ ở `test_load_harness.py` do cần Linux `/proc`, `sched_setaffinity` hoặc quyền tạo symlink); `ruff check .` sạch, `ruff format --check .` (174 files) đạt. Trên CI Linux sẽ chạy đủ 537 passed, 0 skipped, 0 xfailed.
- **Message:** `docs(tasks): record 2026-11-24 member B results (G0)`
- **Commit:** commit này

## Việc chung (không tính commit)

- Review PR ngày 11-24 của A **trong 18 giờ** kể từ lúc A mở, comment trên GitHub. #72 của A (mở 11-24 02:50 UTC) đã merge nhưng vẫn có thể comment.
- Trả lời từng điểm review (nếu có), ghi commit sửa.
