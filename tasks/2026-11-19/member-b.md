# 2026-11-19 · Member B: guard thư mục lưu không được xóa, thư mục lưu cấu hình được, tìm không phân biệt hoa thường, trang quá cuối (Đợt 12, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #67 (B) rồi #66 (A) đã vào `main` (`efbbed9`, `006fd8c`). C chạy lại #67 trên PostgreSQL 16: **500 passed, 0 skipped**. Review của C nằm trên #67.
- **Review:** B review #66 sau khoảng 31 giờ (quá hạn 18 giờ).
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-19. Không phụ thuộc PR của A.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [x] `guard_no_real_appdata_leak` xóa thư mục trong `backend/appdata/audio` thật (BE-16)
- **Lỗi (review #67):** `backend/tests/conftest.py`: guard `shutil.rmtree` mọi thư mục mới trong `appdata/audio` thật trong lúc pytest chạy. API dev hoặc harness tải chạy cùng lúc trên thư mục đó sẽ mất bản ghi âm thật.
- **Làm:** guard chỉ báo lỗi, **không xóa**, và ghi tên các thư mục mới. Test cho guard: tách phần so sánh trước và sau thành hàm, test trên `tmp_path` rằng thư mục mới vẫn còn sau khi guard báo lỗi.
- **Message:** `test(backend): the appdata guard reports a leak without deleting anything (BE-16)`
- **Commit:** `f025ea0`

### 2. [x] Thư mục lưu cố định trong code, test và harness không đổi được (BE-16)
- **Hiện tại:** `LocalStorage()` (`backend/app/services/storage/local.py:31`) luôn dùng `backend/appdata`. Test phải `dependency_overrides` từng chỗ; harness tải (`backend/scripts/load_vt018.py`, `STORAGE`) ghi vào thư mục thật.
- **Làm:** thêm `STORAGE_DIR` vào `Settings`, mặc định giữ đúng `backend/appdata` (Compose không đổi). `LocalStorage()` không tham số dùng `STORAGE_DIR`. `conftest.py` đặt `STORAGE_DIR` sang thư mục tạm cho cả phiên test. Test: mặc định không đổi; đặt biến thì API và worker cùng ghi vào đó. Cập nhật `test_harness_storage_is_where_the_app_writes` nếu cần, không đổi hành vi harness.
- **Message:** `fix(backend): the local storage directory comes from STORAGE_DIR, default unchanged, tests use a temporary one (BE-16)`
- **Commit:** `64cc97f`

### 3. [x] Tìm không phân biệt hoa thường với chữ tiếng Việt (BE-05)
- Test API trên **Postgres**: tiêu đề `Họp nhóm` và `HỌP KỸ THUẬT`. `q=HỌP` → 2, `q=họp` → 2, `q=kỹ` → 1. Postgres của CI và Compose dùng locale UTF-8; ghi locale database vào log.
- Test đỏ trước nếu sai; nếu đúng thì ghi "không có lỗi" và giữ test. Log UTF-8: `docs/evidence/final/meeting-search-case-2026-11-19.log` (không có lỗi).
- **Message:** `test(backend): meeting search ignores case for Vietnamese letters on PostgreSQL (BE-05)`
- **Commit:** `f058b9b`

### 4. [x] Trang quá trang cuối, `page=0`, `page_size` quá 100 (BE-05)
- Test: 11 cuộc họp, `page_size=10`. `page=3` → 200, `items: []`, `total: 11`. `page=0` → 422, `page_size=101` → 422. Kết hợp `q`: trang quá cuối vẫn trả `total` của `q`. Việc 3 của A dựa vào hành vi này.
- **Message:** `test(backend): the meeting list past the last page returns no items with the right total (BE-05)`
- **Commit:** `98d1b12`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy cả backend **trên Postgres**: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`. **Số skipped phải là 0** (11-17 ghi 24 skipped vì chạy không có Postgres).
- Kết quả test: 515 tests thu thập; chạy trên Postgres (CI/test bench): 515 passed, 0 skipped; cục bộ (không daemon Postgres): 490 passed, 25 skipped (cần Postgres/Linux), 0 failed; ruff sạch (171 files).
- **Message:** `docs(tasks): record 2026-11-19 member B results (G0)`
- **Commit:** commit này

## Việc chung (không tính commit)

- Review PR ngày 11-19 của A **trong 18 giờ** kể từ lúc A mở, comment trên GitHub.
- Trả lời từng điểm review (nếu có), ghi commit sửa.
