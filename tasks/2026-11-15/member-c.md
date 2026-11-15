# 2026-11-15 · Member C: chặn bằng chứng không phải UTF-8, hai nghi vấn còn lại ở 40 client, 247 client tách CPU (Đợt 9, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #56 (B) và #57 (A) đã vào `main`. C review diff, gộp thử cả hai, backend 444 passed / 16 skipped (không có Postgres); #56 CI xanh 15/15; #57 chỉ đổi docs nên CI không chạy, C kiểm mọi link tương đối trong file đổi: 0 hỏng. Merge `1e71c89`, `115c905`.
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app. Chỉ thêm test, công cụ đo và bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Test chặn file văn bản trong `docs/`, `tasks/` không phải UTF-8 hoặc có BOM UTF-16 (`reports/` không nằm trong git). Khi review #56 thấy `docs/evidence/final/summary-partial-red-2026-11-13.log` là UTF-16, lần thứ hai sau `deletion-2026-11-12.log` (#54). Test đỏ trước trên `main`, rồi đổi file đó sang UTF-8, nội dung giữ nguyên | `test(docs): evidence and task files must be UTF-8 (G0)` | `28c8883` |
| 2 | [x] 40 client: kiểm hai nghi vấn còn lại của mức chậm ngày 11-12, xen kẽ `base` / `nosync` (Postgres `synchronous_commit=off` qua tham số kết nối) / `fresh` (thư mục audio rỗng, cùng ổ đĩa) / `tmpfs` (thư mục audio rỗng trên `/dev/shm`) | `test(backend): 40-client runs isolating commit fsync and audio writes (VT-018)` | `91eb67a` |
| 3 | [x] 247 client: thêm `--server-cpus` và `--client-cpus` vào harness, có unit test; đo xen kẽ chung CPU / tách CPU ở 1 và 4 process API. Kiểm câu "phần chênh nằm trước middleware và ở máy sinh tải" của ngày 11-11 | `test(backend): 247 clients with the load generator on separate cores (AD-018, AI-19)` | `48574c6` |
| 4 | [x] Sinh lại thời gian phản hồi PR tới #57; bản đồ bằng chứng và ROADMAP theo `main` sau #56, #57 | `docs(evidence): evidence map, PR response times and roadmap after #56, #57 (RE-018, AD-018, VT-018)` | `d772496` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-15 member C results (G0)` | commit này |

## Kết quả và điều còn mở

Ngoài 5 commit: `9cc49eb` (giao việc, PR #58, merge `8c29185` để A và B đọc được trên `main`). Trước đó C review và merge #56, #57.

- **UTF-8 (G0):** test đỏ trên `main` đúng 1 file (log đỏ của #56, BOM UTF-16); sau khi đổi: 2 passed. Cho phép BOM UTF-8 vì PowerShell 5.1 `Out-File -Encoding utf8` ghi BOM.
- **40 client (VT-018):** 16/16 lượt đạt, p95 upload 0,34 đến 0,73 s, 0 lỗi. fsync khi commit (`synchronous_commit=off`) bớt trung bình 0,06 s, đổi dấu ở 1/4 vòng; đĩa hay RAM chênh 0,02 s. Thư mục lưu đầy (18.080 thư mục con) chậm hơn thư mục rỗng khoảng 0,13 s, 4/4 vòng, nhưng thứ tự trong vòng cố định nên còn lẫn với thứ tự chạy. Mức chậm 0,9 s của 11-12 không tái hiện. Gộp 4 ngày: 39/40 lượt đạt.
- **247 client (AD-018):** máy sinh tải chỉ dùng 0,27 đến 0,71 CPU; ghim nó sang nhân riêng không đổi kết quả 1 process. 1 process: 6/6 lượt trên mốc (2,09 đến 2,75 s), **không đạt**. 4 process: 9/9 lượt đạt (1,00 đến 1,37 s). A/B với app 11-11 ra 1,05 đến 1,18 s, nên việc ngày 11-11 không đạt (2,30 đến 2,60 s) không do code. Ghi ◐, không ghi đạt ổn định.
- **Phản hồi PR:** 5/27 PR từ 11-06 có phản hồi của người khác. #56, #57 chờ 44 giờ không ai phản hồi, kể cả nhóm trưởng: quá cả 18 và 20 giờ.
- **Backend:** có Postgres 16: 467 passed, 0 skipped. Ruff sạch.
- **Còn mở:**
  - Nguyên nhân mức chậm 40 client ngày 11-12, và nguyên nhân 247 client ngày 11-11 chậm hơn hôm nay. Khác biệt đã biết: cluster Postgres mới, TCP thay vì Unix socket.
  - 1 process API (cấu hình mặc định) không đạt 247 client. Phần chậm nằm trước middleware, chưa đo riêng.
  - `LocalStorage` cứng thư mục `backend/appdata`, harness không dọn file sau mỗi lượt (2,3 GB trên máy đo).
