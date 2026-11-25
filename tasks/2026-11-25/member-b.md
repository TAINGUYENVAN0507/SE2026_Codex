# 2026-11-25 · Member B: thứ tự job mới nhất, dung lượng audio luôn 0, xóa file theo `STORAGE_DIR`, dẫn chứng của tóm tắt (Đợt 15, sau hạn nộp)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** 5, **đúng 5**. #75 có 6 commit: refactor `bde32b7` không có trong việc được giao. Refactor sau này mở PR riêng.
- **Điều kiện bắt đầu:** #74 (A) và #75 (B) đã vào `main` (`46feb59`, `70b527a`). C gộp hai PR với `main` rồi chạy trên PostgreSQL 16: 536 passed, 1 skipped (`test_db_fixture.py:103` cần Postgres nghe cả IPv4 và IPv6; trên CI là 537 passed, 0 skipped).
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-25. Không phụ thuộc PR của A.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**: `uv run pytest ... 2>&1 | Out-File -Encoding utf8 <file>`.

## Việc

### 1. [ ] Danh sách và chi tiết chọn hai job mới nhất khác nhau khi `created_at` trùng (finding P2 của A trên #75)
- **Lỗi:** `load_latest_jobs_by_meeting` (`backend/app/services/meetings/queries.py`) sắp `created_at DESC, id DESC`. Hai chỗ khác chỉ sắp `created_at DESC`: `serialize_meeting_detail` (dòng 117) và nhánh mặc định của `serialize_meeting_summary` (dòng 57).
- C tái hiện trên PostgreSQL 16 với hai job cùng `created_at`: danh sách trả `latest_job_id = ...002`, chi tiết trả `...001`. Trên `main` trước #75, mọi chỗ đọc sắp giống nhau.
- **Test đỏ trước** (Postgres, timestamp trùng): `GET /meetings`, `GET /meetings/{id}` và `GET /jobs/...` (nếu có chỗ đọc job mới nhất) phải cùng một job.
- **Sửa:** một hàm hoặc hằng thứ tự dùng chung cho mọi chỗ đọc. Test ngân sách truy vấn của #75 phải vẫn xanh.
- **Message:** `fix(backend): every reader picks the same latest job when two jobs share created_at (BE-05)`
- **Commit:** _chưa_

### 2. [ ] `audio.size_bytes` luôn bằng 0 (BE-05, FE-19)
- **Lỗi:** `serialize_meeting_summary` (`queries.py`) ghi cứng `"size_bytes": 0`. Hợp đồng (`MeetingAudioOut.size_bytes`, `contracts/openapi.json`) ghi đây là dung lượng file, cho phép `null`.
- **Test đỏ trước:**
  - Upload một WAV có kích thước biết trước vào storage tạm. `GET /meetings/{id}` trả đúng số byte.
  - Không còn audio (`audio_path` là null, hoặc file đã bị xóa theo hạn lưu) thì `size_bytes` là `null` và `available` là false.
- **Sửa:** lấy kích thước qua storage, không mở file. Danh sách 10 mục không được tăng số truy vấn DB (chạy lại test ngân sách truy vấn).
- **Message:** `fix(backend): meeting audio reports its real size instead of 0 (BE-05, FE-19)`
- **Commit:** _chưa_

### 3. [ ] Xóa cuộc họp xóa file trong đúng `STORAGE_DIR` (chuyển từ 11-23, việc 3)
- Như `tasks/2026-11-23/member-b.md`, việc 3:
  - Upload vào `STORAGE_DIR` đặt sang `tmp_path`, rồi `DELETE /meetings/{id}`.
  - `audio/<id>` và `artifacts/<id>` mất.
  - Cuộc họp khác còn nguyên, `backend/appdata` thật không đổi.
- **Message:** `test(backend): deleting a meeting removes its files from STORAGE_DIR and nothing else (BE-16, AD-018)`
- **Commit:** _chưa_

### 4. [ ] `PUT /summary` nhận `evidence_segment_ids` không thuộc cuộc họp (BE-05, FE-18)
- **Lỗi (C tìm ngày 11-25):** `PUT /meetings/{id}/summary` với `evidence_segment_ids` là một UUID không tồn tại trả **200** và lưu vào tóm tắt. Dẫn chứng của biên bản (FE-18) vì thế có thể trỏ tới segment không có, hoặc segment của cuộc họp khác.
- Test: `backend/tests/integration/test_field_limits_postgres.py`, ca `put-summary-evidence-id-unknown`, đang đánh `xfail(strict=True)`.
- **Sửa:**
  - Mọi id trong `key_points[].evidence_segment_ids` và `decisions[].evidence_segment_ids` phải là segment của chính cuộc họp đó, sai thì 422 với mã lỗi riêng. Thêm mã vào `contracts/error_codes.md`.
  - Thêm ca "segment của cuộc họp khác".
  - **Bỏ dấu xfail** của ca trên. Dấu là `strict=True`, nên sau khi sửa ca đó chuyển sang XPASS và làm suite đỏ nếu chưa bỏ.
- **Message:** `fix(backend): summary evidence must point at segments of the same meeting (BE-05, FE-18)`
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này". Ghi "xong ở 11-25" vào ô việc 3 của `tasks/2026-11-23/member-b.md`.
- Chạy cả backend **trên Postgres** nghe cả IPv4 và IPv6. Ghi số passed, **skipped 0, xfailed 0**. Ruff check và format sạch.
- **Message:** `docs(tasks): record 2026-11-25 member B results (G0)`
- **Commit:** _chưa_

## Việc chung (không tính commit)

- Review PR ngày 11-25 của A **trong 18 giờ** kể từ lúc A mở, comment trên GitHub.
- Trả lời từng điểm review (nếu có), ghi commit sửa.
