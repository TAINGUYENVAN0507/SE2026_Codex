# 2026-11-23 · Member C: harness ghi vào thư mục lưu trống, tìm kiếm có và không xen kẽ ở 247 client, 40 client với thư mục trống và thật (Đợt 13, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** C review diff #69 (A) và #70 (B), CI xanh 12/12 và 15/15, rồi merge `9a87355` và `5c29101`.
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app; chỉ test, công cụ đo, bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Harness có `--storage temp` (mặc định) và `--storage real`. Với `temp`, API và worker ghi vào thư mục trống của lượt qua `STORAGE_DIR` (app đọc biến này từ #70). Harness luôn đặt `STORAGE_DIR`, ghi đè giá trị có sẵn, và xóa thư mục tạm của lượt khi xong (trước đây để lại trong `/tmp`). Có unit test cho đường dẫn và cho biến môi trường mà app đọc. Chạy thử 5 client ở cả hai chế độ: `backend/appdata` thật không đổi | `test(backend): load harness writes to an empty STORAGE_DIR per run, not backend/appdata, and removes its temp folder (AD-018, VT-018, BE-16)` | `c34ed5c` |
| 2 | [x] 247 client, 2 process, có và không có tìm kiếm xen kẽ ABBA ABBA, 8 lượt | `test(backend): 247 clients on 2 API processes with and without meeting search interleaved on main after #69 and #70 (AD-018, BE-05)` | `5e43185` |
| 3 | [x] 40 client có tìm kiếm, thư mục lưu trống và thật xen kẽ ABBAAB, 6 lượt | `test(backend): 40 clients with an empty and the real storage folder interleaved on main after #69 and #70 (VT-018)` | `e479603` |
| 4 | [x] Bản đồ bằng chứng, ROADMAP (thêm kết quả Đợt 12 và Đợt 13), thời gian phản hồi PR tới #70; giao việc 11-23 | `docs(evidence): evidence map, PR response times and roadmap after #69 and #70; assign 2026-11-23 (RE-018, AD-018, VT-018)` | `7c250b9` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-23 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **Review #69:** đọc diff, không có điểm chặn. `setPage` gọi trong lúc render có điều kiện chặn, nên không lặp.
- **Review #70:** chạy lại trên PostgreSQL 16: 515 passed, 0 skipped, `backend/appdata` thật không đổi.
  - Finding P2 của A đúng: trên cùng một server nghe cả hai địa chỉ, `_check_postgres_connection` trả True với `127.0.0.1` và False với `[::1]`. Lỗi chỉ ở phần chuẩn bị test, nên C merge và giao sửa cho B (việc 1).
  - Bước preflight không có trong việc được giao ngày 11-19.
- **Lỗi mới C thấy khi soạn việc:**
  - "Xóa bộ lọc" vẫn gửi từ khóa cũ thêm 300 ms. Giao A.
  - Lúc đang tải hoặc lỗi, tiêu đề ghi "0 cuộc họp". Giao A.
  - Sang trang thì thanh phân trang biến mất trong lúc tải. Giao A.
  - Worker dự phòng ghi artifact vào `./appdata` tương đối (`runner.py` dòng 273). Giao B.
  - N+1 ở `GET /meetings`. Giao B.
- **247 client, 2 process, xen kẽ:**
  - Không tìm kiếm: 1,38 đến 2,01 s, đạt 3/4.
  - Có tìm kiếm: 1,61 đến 1,89 s, đạt 4/4.
  - Chênh trung bình khoảng 0,1 s, nhỏ hơn dao động trong cùng điều kiện (0,63 s). Lượt 2,52 s ngày 11-19 vì vậy khó giải thích bằng tìm kiếm.
  - 3.952 lượt tìm, 0 kết quả sai, 0 dòng có query string.
- **40 client:** 6/6 đạt (0,39 đến 0,66 s). Thư mục trống trung bình 0,43 s, thư mục thật 0,49 s, chênh chủ yếu do một lượt. Gộp 8 ngày: 69/70.
- **Phản hồi PR:** 12/39 PR có phản hồi của người khác, 8/12 trong 18 và 20 giờ. B approve #69 sau 8,0 giờ. A review #70 sau 63,3 giờ.
- **Backend (PostgreSQL 16, `main` + 4 commit của C):** 517 passed, 0 skipped. Ruff sạch (171 file). `backend/appdata/audio` giữ 22.950 thư mục trước và sau khi chạy.
- **Còn mở:**
  - Sau khi B sửa N+1, đo lại 247 client có tìm kiếm.
  - `API_WORKERS: 1` mặc định không đạt 247 client.
  - Lượt 1,56 s ngày 11-12 chưa rõ nguyên nhân.
  - Khoảng 22.934 thư mục WAV của harness cũ trong `backend/appdata` trên máy đo, C chưa xóa vì chưa được đồng ý. Từ hôm nay harness không ghi thêm vào đó nữa.
