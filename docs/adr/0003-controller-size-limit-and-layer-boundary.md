# ADR 0003: Giới hạn kích thước Controller và Ranh giới phân tầng API - Worker (AD-018)

- **Trạng thái:** Accepted
- **Ngày quyết định:** 2026-11-10
- **Người đề xuất:** Member B (`@minhquangha`)
- **Phạm vi áp dụng:** Toàn bộ API routers trong `backend/app/api/v1/`

---

## 1. Bối cảnh (Context)

Trong giai đoạn phát triển ban đầu, `backend/app/api/v1/meetings.py` từng phình to lên tới 2.412 dòng và sau đó là 946 dòng. Tương tự, `action_items.py` đạt 558 dòng code. Các controller lớn này có các vấn đề nghiêm trọng:
1. **Vi phạm Single Responsibility Principle:** Một module vừa định nghĩa endpoint, vừa xử lý upload file, vừa gọi `ffprobe` trích xuất âm thanh, vừa quản lý transaction DB, vừa dựng schema phản hồi và kiêm nhiệm cả các route của subdomain khác (`speakers`, `edits`, `summary`).
2. **Khó bảo trì và dễ gây xung đột Git:** Nhiều thành viên cùng sửa trên một file controller lớn làm tăng nguy cơ merge conflict và làm chậm chu kỳ phát triển.
3. **Nguy cơ xóa nhòa ranh giới kiến trúc:** Khi controller quá lớn, nguy cơ gọi trực tiếp các thành phần nền của Worker (`app.worker.runner`, `pipeline`) thay vì thông qua cơ chế hàng đợi DB chuẩn hóa.

## 2. Quyết định (Decision)

1. **Giới hạn kích thước tối đa 500 dòng code cho mỗi module controller trong `app/api/v1/`:**
   - Mỗi file controller (`*.py`) trong `app/api/v1/` không được vượt quá 500 dòng.
   - Khi module có xu hướng vượt quá 500 dòng, bắt buộc phải:
     - Tách các nhóm route con sang controller riêng (ví dụ: `speakers.py`, `edits.py`, `audio.py`, `segments.py`, `summary.py`, `export.py`).
     - Chuyển logic nghiệp vụ, xử lý storage, tính toán và validation phức tạp xuống tầng Service (`app/services/meetings/upload.py`, `app/services/action_items.py`).
     - Tái sử dụng các serializer chuẩn hóa (ví dụ: `serialize_job`, `serialize_action_item`).

2. **Cấm tuyệt đối API Controller import `app.worker`:**
   - Các route module trong `app/api/v1/` không được import trực tiếp bất kỳ thành phần nào từ `app.worker`.
   - Mọi tương tác giữa API và Worker phải tuân thủ ranh giới qua cơ sở dữ liệu: API tạo bản ghi `Job` ở trạng thái `queued`, Worker runner định kỳ claim job thông qua cơ chế khóa lease hàng đợi (`app/worker/queue.py`).

3. **Bảo vệ bằng Kiểm thử Kiến trúc Tự động:**
   - Thiết lập test kiến trúc tự động `backend/tests/unit/test_controller_limits.py` chạy trong bộ CI test.
   - Bất kỳ controller nào phình vượt quá 500 dòng hoặc import `app.worker` sẽ lập tức làm đỏ CI và bị từ chối merge.

## 3. Hệ quả (Consequences)

- **Tích cực:**
  - `meetings.py` giảm từ 946 dòng xuống còn 455 dòng; `action_items.py` giảm từ 558 dòng xuống 452 dòng.
  - Mã nguồn controller trong sáng, chỉ tập trung vào nhiệm vụ điều hướng HTTP (parse request, validate, gọi service, trả response).
  - Ngăn ngừa tình trạng phình code trở lại trong tương lai nhờ test kiến trúc giữ chốt.
- **Tiêu cực / Ràng buộc:**
  - Lập trình viên phải dành thêm thời gian thiết kế tầng service và router con khi thêm tính năng mới thay vì viết gộp vào controller.
