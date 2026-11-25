# 2026-11-23 · Member B: preflight Postgres IPv6, N+1 ở danh sách cuộc họp, xóa cuộc họp theo `STORAGE_DIR`, đường dẫn dự phòng của worker (Đợt 13, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #69 (A) và #70 (B) đã vào `main` (`9a87355`, `5c29101`). C chạy lại #70 trên PostgreSQL 16: **515 passed, 0 skipped**, `backend/appdata` thật không đổi. Review của C nằm trên #70.
- **Review:** B approve #69 sau 8,0 giờ, trong hạn.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-23. Không phụ thuộc PR của A.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [ ] Preflight trong `conftest.py` coi PostgreSQL IPv6 là "không có Postgres" (finding P2 của A trên #70)
- **Lỗi:** `_check_postgres_connection` (`backend/tests/conftest.py`) mở socket `AF_INET` tới host trong URL. Với `postgresql+psycopg://...@[::1]:<port>/...`, socket không nhận `::1`, nên hàm trả False dù Postgres chạy. Kết quả: test bị skip ở local, hoặc fail "cần Postgres" trên CI. C tái hiện được: cùng một server, `127.0.0.1` cho True, `[::1]` cho **False**.
- **Test đỏ trước:**
  - Test unit, không cần DB thật: mở một socket nghe trên `::1` (bỏ qua nếu máy không có IPv6), kiểm bước preflight nhận được kết nối.
  - Test so sánh hai URL `127.0.0.1` và `[::1]` trên Postgres thật, chạy nếu Postgres nghe cả hai địa chỉ.
- **Sửa:** dùng `socket.create_connection` (hỗ trợ cả IPv4 và IPv6) hoặc bỏ bước socket riêng. Ghi trong commit vì sao #70 thêm preflight; nó không có trong việc được giao ngày 11-19.
- **Message:** `fix(backend): the test Postgres preflight accepts IPv6 hosts (BE-16, G0)`
- **Commit:** chuyển sang 11-24

### 2. [ ] `GET /meetings` chạy một truy vấn `Job` cho mỗi cuộc họp trong trang (BE-05, AD-018)
- **Lỗi:** `list_meetings` gọi `serialize_meeting_summary(m, db)` (`backend/app/api/v1/meetings.py`, dòng 164) cho từng cuộc họp mà không có `latest_job`, nên mỗi mục chạy thêm một `select(Job)` (dòng 70). Trang 10 mục tốn 12 truy vấn. C đo dưới tải: 247 client có tìm kiếm chậm hơn ở 1 và 2 process (`docs/evidence/load-247/search-2026-11-19/README.md`).
- **Test đỏ trước** trong `backend/tests/api/test_poll_query_budget.py`: đếm truy vấn của `GET /meetings` với 1 và 10 mục (có và không có `q`). Số truy vấn phải bằng nhau và không quá 4.
- **Sửa:** lấy job mới nhất của mọi cuộc họp trong trang bằng một truy vấn, rồi truyền `latest_job`. Response của danh sách phải giữ nguyên (test hợp đồng, `contracts/openapi.json`).
- **Message:** `fix(backend): the meeting list loads the latest job of every meeting in one query (BE-05, AD-018)`
- **Commit:** chuyển sang 11-24

### 3. [ ] Xóa cuộc họp xóa file trong đúng `STORAGE_DIR` (BE-16, AD-018)
- #70 mới có test unit cho `STORAGE_DIR`. Viết test API:
  - Đặt `STORAGE_DIR` sang `tmp_path`, upload một cuộc họp, rồi `DELETE /meetings/{id}`.
  - Thư mục `audio/<id>` và `artifacts/<id>` trong `tmp_path` phải mất.
  - `backend/appdata` thật không đổi.
  - Cuộc họp khác trong cùng `tmp_path` còn nguyên.
- Test đỏ trước nếu sai; nếu đúng thì ghi "không có lỗi" và giữ test.
- **Message:** `test(backend): deleting a meeting removes its files from STORAGE_DIR and nothing else (BE-16, AD-018)`
- **Commit:** xong ở 11-25

### 4. [ ] Worker dự phòng ghi artifact vào `appdata` tương đối theo thư mục đang chạy (BE-16)
- **Lỗi:** `backend/app/worker/runner.py` dòng 273 có `getattr(storage, "base_dir", Path("appdata"))`. Nếu storage không có `base_dir`, artifact rơi vào `./appdata` của thư mục đang chạy, không theo `STORAGE_DIR`.
- **Test đỏ trước:** dùng storage giả không có `base_dir`, đặt `STORAGE_DIR` sang `tmp_path`, chạy một job fake. Artifact phải nằm trong `tmp_path`. Sửa bằng `get_settings().STORAGE_DIR`.
- **Message:** `fix(backend): the worker falls back to STORAGE_DIR, not a relative appdata folder, for artifacts (BE-16)`
- **Commit:** chuyển sang 11-24

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy cả backend **trên Postgres**: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`. **Số skipped phải là 0.**
- **Message:** `docs(tasks): record 2026-11-23 member B results (G0)`
- **Commit:** chuyển sang 11-24

## Việc chung (không tính commit)

- Review PR ngày 11-23 của A **trong 18 giờ** kể từ lúc A mở, comment trên GitHub.
- Trả lời từng điểm review (nếu có), ghi commit sửa.
