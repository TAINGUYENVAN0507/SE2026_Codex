# 2026-11-19 · Member C: tìm kiếm `?q=` dưới tải, 247 và 40 client sau #67 và #66 (Đợt 12, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** C review diff #67 (B) và #66 (A). CI xanh 16/16 và 12/12. Merge `efbbed9` rồi `006fd8c` (#67 trước).
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app; chỉ test, công cụ đo, bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Harness có `--search K`. Sau upload, mỗi client gửi K lượt `GET /meetings?q=`, xoay vòng `%`, `_`, `100%` và tiêu đề của client. Wildcard phải ra 0 kết quả, tiêu đề phải ra ít nhất 1, sai thì tính `search_wrong`. Có dòng tìm kiếm trong `summary.md`. Unit test có API giả: một ca đúng và một ca như trước #67 | `test(backend): load harness searches the meeting list with % and _ under load and counts wrong results (AD-018, BE-05, BE-19)` | `dde0a52` |
| 2 | [x] 247 client có `--search 4`, 1, 2 và 4 process, 3 vòng xoay vòng, trên `main` sau #67 và #66, kèm lượt đối chứng 5 client trên `dddbdef` (trước #67) | `test(backend): 247 clients with meeting search on 1, 2 and 4 API processes on main after #66 and #67, with a pre-#67 control (AD-018, BE-05, BE-19)` | `36d53c0` |
| 3 | [x] 40 client có `--search 4`, 6 lượt, thư mục lưu thật | `test(backend): 40 clients with meeting search on main after #66 and #67 (VT-018)` | `4106e54` |
| 4 | [x] Bản đồ bằng chứng, ROADMAP (thêm kết quả Đợt 11 và Đợt 12), thời gian phản hồi PR tới #67; giao việc 11-19 | `docs(evidence): evidence map, PR response times and roadmap after #67 and #66; assign 2026-11-19 (RE-018, AD-018, VT-018)` | `b66b285` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-19 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **Review #67:** đọc diff, chạy lại trên PostgreSQL 16: 500 passed, 0 skipped. Không có điểm chặn merge. Hai điểm chuyển thành việc của B: guard `shutil.rmtree` thư mục mới trong `backend/appdata/audio` thật; B ghi 24 skipped thay vì chạy trên Postgres.
- **Review #66:** gộp với `main` (có #67), chạy E2E wildcard `--retries=0` 3 lượt, mỗi lượt một database e2e mới: 3/3 passed. `%`, `_`, `100%` mỗi từ khóa ra đúng 1. Chuyển #66 khỏi Draft rồi merge. A tick việc 1 ngày 11-17 bằng lượt do A tự chạy (việc 1 của A hôm nay).
- **Lỗi mới C thấy khi soạn việc:**
  - Ô tìm không có `maxLength`, nên từ #67 dán quá 200 ký tự thì API trả 422. Giao A, việc 2.
  - Bộ lọc trạng thái không có mục nào nhưng màn hình báo "Chưa có cuộc họp". Giao A, việc 4.
  - `LocalStorage()` cố định `backend/appdata`. Giao B, việc 2.
- **247 client có tìm kiếm:** 0 lỗi và 0 kết quả tìm sai trong 8.892 lượt tìm.
  - 1 process: 3/3 trên mốc (2,28 đến 3,02 s).
  - 2 process: 2/3 đạt (1,48 và 1,70 s; 1 lượt 2,52 s). Ngày 11-17, không có tìm kiếm: 3/3 đạt.
  - 4 process: 3/3 đạt (1,10 đến 1,15 s).
  - Load máy hôm nay cao hơn 11-17, nên chưa tách được phần chậm do tìm kiếm và phần do máy.
- **Đối chứng trước #67:** 10/20 lượt tìm sai (`%` 5, `_` 5), nên harness bắt được lỗi cũ.
- **Log dưới tải có `?q=`:** mỗi lượt 247 client có 2.969 dòng stdout của API, 0 dòng access của uvicorn, 0 dòng có query string. Đây là phần còn thiếu của kiểm log ngày 11-17.
- **40 client có tìm kiếm:** 6/6 đạt (0,38 đến 0,49 s). Gộp 7 ngày: 63/64.
- **Phản hồi PR:** 10/36 PR có phản hồi của người khác, 7/10 trong 18 và 20 giờ. B review #66 sau 31,4 giờ (quá hạn). A không review #67.
- **Backend (PostgreSQL 16, `main` + 4 commit của C):** lượt đầu 1 failed, 507 passed. `test_evidence_map_links` bắt được đường dẫn `meetings.py:70` trong bản đồ bằng chứng. C sửa thành "dòng 70" trong commit 4 (amend trước khi push), chạy lại: **508 passed, 0 skipped**. Ruff sạch. `backend/appdata/audio` giữ 22.950 thư mục trước và sau khi chạy (guard của #67 không bắt rò).
- **Còn mở:**
  - `GET /meetings` chạy 1 truy vấn `Job` cho mỗi cuộc họp trong trang (N+1, `backend/app/api/v1/meetings.py` dòng 70) và chưa có test ngân sách truy vấn. Chưa giao, để đợt sau.
  - `API_WORKERS: 1` mặc định không đạt 247 client.
  - Lượt 1,56 s ngày 11-12 chưa rõ nguyên nhân.
  - Khoảng 22.934 thư mục WAV của harness cũ trong `backend/appdata` trên máy đo. C chưa xóa vì chưa được đồng ý.
