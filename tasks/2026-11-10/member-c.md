# 2026-11-10 · Member C: test không phụ thuộc máy, tách độ trễ client và server, đo lại 247 (Đợt 5)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 10.
- **Điều kiện bắt đầu:** #44 và #45 đã vào `main` (C review và merge ngày 2026-11-10).
- **Mục tiêu:**
  1. 5 test upload đỏ trên máy có ffprobe nhưng xanh trên CI (CI không có ffprobe nên chạy bản mock). Bộ test phải ra cùng kết quả ở mọi máy.
  2. Số đo 247 client hiện gộp chung thời gian chờ ở client, chờ ở hàng đợi admission và thời gian xử lý. Cần tách ba phần đó trước khi kết luận điều gì về p95 ≤ 2,0 s.
  3. Đo lại 247 trên `main` sau thay đổi của B (6 query/upload, `API_WORKERS`) và ghi kết quả thật.

PR này thuộc VT-018: **không merge khi chưa có review của B.**

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [ ] Test upload dùng WAV hợp lệ, xanh cả khi có và không có ffprobe (VT-018, flaky theo môi trường); log đỏ trước | `test(backend): upload tests pass with or without ffprobe on the machine (VT-018)` | |
| 2 | [ ] CI backend cài ffmpeg để chạy đường probe thật; test báo lỗi nếu CI thiếu ffprobe | `ci(backend): run the real ffprobe path in CI (VT-018, BE-15)` | |
| 3 | [ ] Histogram `api_admission_wait_seconds`: thời gian request chờ ở hàng đợi admission; test đỏ trước (RE-018, AD-018) | `feat(backend): measure how long requests wait for admission (RE-018, AD-018)` | |
| 4 | [ ] Harness đọc `/metrics` trước và sau lượt đo: p95 phía server (xử lý, chờ admission) đặt cạnh p95 phía client (AI-19) | `test(backend): load harness reports server-side latency next to client-side (AI-19)` | |
| 5 | [ ] Harness chia client ra nhiều process để máy sinh tải không thành nút cổ chai; so sánh 1 và nhiều process client trên cùng cấu hình server (AI-19) | `test(backend): load harness can spread clients over several processes (AI-19)` | |
| 6 | [ ] Đo lại 247 trên `main` sau #45: 1 và 4 process API, 3 lần mỗi cấu hình, kèm phần tách client/server (AD-018) | `test(backend): re-measure 247 clients on main after the upload query cut (AD-018, AI-19)` | |
| 7 | [ ] Đo lại 239 và 40 trên `main` (hồi quy) (RE-018, VT-018) | `test(backend): re-measure 239 and 40 clients on main (RE-018, VT-018, AI-19)` | |
| 8 | [ ] Bảng thời gian phản hồi PR (mở → review đầu tiên → merge) sinh từ GitHub, kèm script; ghi đúng các PR merge không có review (RE-018 20 giờ, AD-018 18 giờ) | `docs(evidence): PR response times from GitHub, with the script (RE-018, AD-018)` | |
| 9 | [ ] ROADMAP: cột "Hiện trạng" của ba bảng yêu cầu theo code hiện tại (bảng đang ghi theo `53f753b` ngày 11-06) | `docs(tasks): requirement status in the roadmap matches main (G0)` | |
| 10 | [ ] Bản đồ bằng chứng, kết quả, hash | `docs(evidence): evidence map and 2026-11-10 member C results (G0)` | |

## Kết quả và điều còn mở

(điền khi xong)
