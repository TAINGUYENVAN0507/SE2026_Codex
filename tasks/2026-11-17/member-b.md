# 2026-11-17 · Member B: tìm kiếm không hiểu `%` và `_`, test ghi vào thư mục lưu thật, số liệu người nói sau khi sửa (Đợt 11, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #61 (B) và #64 (A) đã vào `main` (`8fcf72e`, `1dc6b5c`). A review #61 sau 4,4 giờ; B không review #60 của A.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-17. **PR của B merge trước PR của A**, vì E2E của A (việc 1) cần việc 1 dưới đây.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [x] `GET /meetings?q=` coi `%`, `_`, `\` là ký tự đại diện (BE-05, FE-04)
- **Lỗi:** `backend/app/api/v1/meetings.py:145`: `Meeting.title.ilike(f"%{q.strip()}%")`. `q=%` ra mọi cuộc họp; `q=_` ra mọi tiêu đề; `q=100%` ra mọi tiêu đề chứa `100`. Từ #64 người dùng gõ vào ô tìm là gửi thẳng lên đây.
- **Test đỏ trước** (`backend/tests/api/test_meeting_list_detail.py`, chạy được trên SQLite và Postgres): 3 meeting `Giảm 100% chi phí`, `Họp_nhóm`, `Họp nhóm`, `Họp 100 người`. `q=%` → 1, `q=_` → 1, `q=100%` → 1, `q=\` → 0, `q=100` → 2. Log đỏ: `docs/evidence/final/meeting-search-wildcard-red-2026-11-17.log`.
- **Sửa:** escape `\`, `%`, `_` rồi `ilike(..., escape="\\")`. Thêm giới hạn độ dài của `q` (`max_length=200`) ở `Query`; `q` dài hơn trả 422 theo envelope lỗi chung. Cập nhật `contracts/` và `openapi.json` nếu đổi, kiểm không drift.
- **Message:** `fix(backend): meeting search matches % and _ literally and bounds q (BE-05, FE-04)`
- **Commit:** `1cd8818`

### 2. [x] Test hợp đồng ghi file vào `backend/appdata` thật (BE-16)
- **Lỗi:** `backend/tests/contract/test_openapi_drift.py:488` `test_create_meeting_success` dựng `create_app()` mà không đổi thư mục lưu, nên mỗi lần chạy backend ghi một thư mục audio (16 byte) vào `backend/appdata` của người chạy. C đếm được 15 thư mục như vậy trên máy đo.
- **Test đỏ trước:** một test (hoặc fixture `autouse` ở `backend/tests/conftest.py`) so danh sách `backend/appdata/audio` trước và sau cả phiên pytest, đỏ nếu thêm thư mục. Cho thấy nó đỏ trên `main` hiện tại. Log đỏ: `docs/evidence/final/contract-storage-leak-red-2026-11-17.log`.
- **Sửa:** test dùng thư mục tạm (override storage hoặc biến môi trường như các test API khác). Không xóa gì trong `backend/appdata` của người khác.
- **Message:** `test(backend): the contract test writes to a temporary storage, not backend/appdata (BE-16)`
- **Commit:** `bd5c2f4`

### 3. [x] `q` kết hợp `status` và phân trang: `total` và các trang khớp nhau (BE-05)
- Test API: 25 meeting, 12 khớp `q`, trong đó 5 ở trạng thái `failed`. Kiểm `q` + `status=failed` → `total=5`; `q` trang 1/2/3 với `page_size=5` → 5, 5, 2 mục, không trùng, không sót; meeting của người dùng khác có cùng tiêu đề không lọt vào (so sánh `total`).
- `test_poll_query_budget.py` phải vẫn xanh.
- **Message:** `test(backend): meeting list total and pages agree when q and status are combined (BE-05)`
- **Commit:** `29aeb4d`

### 4. [x] Số liệu người nói đúng sau khi sửa đoạn hoặc đổi người nói (BE-05)
- #61 đã tính `segment_count` và `speaking_time_sec` ở transcript và meeting detail. Chưa có test cho trường hợp **sau khi sửa**: `PATCH` một đoạn sang người nói khác thì cả hai endpoint và `PATCH /speakers/{id}` phải thống nhất (số đoạn của người cũ giảm 1, người mới tăng 1, tổng thời gian khớp).
- Test đỏ trước nếu có chỗ sai; nếu đúng thì ghi "không có lỗi" và giữ test. Log UTF-8: `docs/evidence/final/speaker-stats-segment-move-2026-11-17.log` (không có lỗi).
- **Message:** `test(backend): speaker stats stay consistent across endpoints after a segment moves to another speaker (BE-05)`
- **Commit:** `fb5c5b5`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy cả backend **trên Postgres**: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`. Ghi số test và số skipped (phải 0 khi có Postgres).
- Kết quả test cục bộ: 476 passed, 24 skipped (cần Postgres/Linux), 0 failed (500 tests); ruff sạch (168 files).
- **Message:** `docs(tasks): record 2026-11-17 member B results (G0)`
- **Commit:** commit này

## Việc chung (không tính commit)

- Review PR ngày 11-17 của A trong 18 giờ kể từ lúc A mở, ghi comment trên GitHub (khác 11-15: #60 không có review của B).
- Trả lời từng điểm review (nếu có), ghi commit sửa.
