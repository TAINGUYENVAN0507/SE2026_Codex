# Hướng dẫn chạy Test và Tái lập Thực nghiệm (VT-017)

**Bài tập cá nhân 3 – AI-assisted Software Development & Software Testing**
- **Sinh viên:** Hà Minh Quang — Mã SV: 23001916
- **Nhóm:** SE2026-T05 (Thành viên / Member B)
- **Mã biến thể:** VT-017
- **Đề tài:** AI-05 – Vietnamese Meeting Minutes Assistant
- **Nhánh thực hiện:** `feat/vt-017-stable-search-pagination`
- **Baseline commit:** `2dea2bfdfea220d0492cedbd56d30340ed41f0b6`

---

## 1. Yêu cầu Môi trường

- Python 3.12+
- `uv` (Fast Python package manager)
- Hệ điều hành: Windows, macOS hoặc Linux

---

## 2. Hướng dẫn Chạy Kiểm thử Đơn vị & Tích hợp (16 Test Cases)

Di chuyển vào thư mục `backend/` và thực thi lệnh:

```bash
cd backend
uv run pytest tests/api/test_meeting_search_pagination.py -v
```

Kiểm tra hợp đồng OpenAPI và không bị drift:

```bash
uv run pytest tests/contract/test_openapi_drift.py -v
```

Kiểm tra toàn bộ test suite của backend:

```bash
uv run pytest -q
```

Kiểm tra định dạng và quy chuẩn mã nguồn:

```bash
uv run ruff check .
uv run ruff format --check .
```

---

## 3. Hướng dẫn Chạy Kiểm chứng Tải (100 Tác vụ đồng thời, p95 <= 3.0s)

Harness kiểm chứng tải được cấu hình sẵn tại `backend/scripts/run_load_test.py`:

```bash
cd backend
uv run python scripts/run_load_test.py
```

**Kết quả thực nghiệm thực tế:**
- Số tác vụ đồng thời: 100 tác vụ
- Tỷ lệ thành công: 100/100 (100%)
- **Độ trễ p95 đạt được: 1135.54 ms (1.14 s)**, vượt chuẩn mục tiêu p95 <= 3.0 s (3000 ms).
- Thông lượng: 61.42 requests/giây.

---

## 4. Tái lập Thử nghiệm Mutation / Deliberate Bug

Mutation bắt buộc: **Bỏ kiểm tra authorization / owner_id ở một đường đi tìm kiếm**.

Để tái lập:
1. Trong file `backend/app/services/meeting_search.py`, sửa dòng 55 thành:
   ```python
   if q and q.strip():
       base_query = select(Meeting)  # Bỏ kiểm tra owner_id khi có tham số q
   else:
       base_query = select(Meeting).where(Meeting.owner_id == owner_id)
   ```
2. Chạy test case cô lập dữ liệu:
   ```bash
   uv run pytest tests/api/test_meeting_search_pagination.py -k test_failure_path_owner_scoping_isolation
   ```
3. **Kết quả:** Test phát hiện lỗi vi phạm ngay lập tức (`assert 1 == 0`, User A đọc được cuộc họp của User B) -> Mutation bị tiêu diệt (Killed).
4. Hoàn nguyên code sạch sau khi thử nghiệm.
