# 2026-11-17 · Member C: harness đếm log của API, 247 và 40 client sau #61 và #64 (Đợt 11, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** C review diff #61 (B) và #64 (A), CI xanh 18/18 và 15/15, merge `8fcf72e` rồi `1dc6b5c` (#61 trước).
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app; chỉ test, công cụ đo, bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Harness đưa stdout của API vào file tạm, đếm dòng access của app, của uvicorn và dòng có query string (`api_log` trong `summary.json`, một dòng trong `summary.md`), rồi bỏ file. Unit test cả hai kiểu dòng | `test(backend): load harness counts the API log lines and any query string under load (AD-018, BE-19)` | `bacc9c3` |
| 2 | [x] 247 client, 1, 2 và 4 process, 3 vòng xoay vòng, trên `main` sau #61 và #64 | `test(backend): 247 clients on 1, 2 and 4 API processes on main after #61 and #64, with the API log counted (AD-018, BE-19)` | `37d2660` |
| 3 | [x] 40 client, 6 lượt, thư mục lưu thật | `test(backend): 40 clients on main after #61 and #64 (VT-018)` | `491c2a7` |
| 4 | [x] Bản đồ bằng chứng, ROADMAP (thêm Đợt 11), thời gian phản hồi PR tới #64; giao việc 11-17 | `docs(evidence): evidence map, PR response times and roadmap after #61 and #64; assign 2026-11-17 (RE-018, AD-018, VT-018)` | `f9ab601` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-17 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **Review #61, #64:** đọc diff, không có điểm chặn. Ghi nhận: `docker-compose.yml` dòng 36 (`API_WORKERS`) và 38 (`--no-access-log`) đã lệch so với số dòng cũ trong README ngày 11-16 (giữ nguyên, vì đó là số dòng tại `3ed9c0d`).
- **Lỗi mới C thấy khi đọc diff:** `meetings.py:145` `ilike(f"%{q}%")` không escape `%`, `_` — từ #64 người dùng gõ là gửi lên đây. Giao B (việc 1) và A (E2E, việc 1).
- **Lỗi đã có từ trước:** `test_create_meeting_success` ghi vào `backend/appdata` thật: lần chạy backend đầy đủ hôm nay làm thư mục audio từ 22.949 lên 22.950. Giao B (việc 2).
- **247 client:** 1 process 3/3 trên mốc (2,12 đến 2,29 s); 2 process 3/3 đạt (1,38 đến 1,41 s); 4 process 3/3 đạt (1,01 đến 1,11 s); 0 lỗi. Stdout API: 1.981 dòng, 0 dòng access của uvicorn, 0 dòng có query string.
- **40 client:** 6/6 đạt (0,41 đến 0,55 s). Gộp 6 ngày: 57/58.
- **Bản đồ:** "Log không giữ dữ liệu cá nhân" đổi từ Một phần sang Có, kèm hai điều kiện ghi rõ (nginx kiểm bằng CI, không chạy cục bộ vì máy đo không có Docker daemon; log container trước 11-16 từng ghi query string).
- **Phản hồi PR:** 8/33 PR có phản hồi của người khác, 6/8 trong 18 và 20 giờ. B review #64 sau khoảng 1 giờ.
- **Backend (Postgres 16):** 494 passed ở `main` trước commit 1, ruff sạch; sau commit 1 chạy lại `tests/unit`: 254 passed.
- **Còn mở:** `API_WORKERS: 1` mặc định không đạt 247 client (2 process đạt ở 2 ngày, chưa đo trên Compose); nguyên nhân lượt 1,56 s ngày 11-12 và 247 client ngày 11-11; 22.934 thư mục WAV của harness trong `backend/appdata` trên máy đo (C chưa xóa vì chưa được đồng ý).
