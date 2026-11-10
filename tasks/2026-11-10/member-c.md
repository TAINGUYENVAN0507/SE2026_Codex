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
| 1 | [x] Test upload dùng WAV hợp lệ, xanh cả khi có và không có ffprobe (VT-018, flaky theo môi trường); log đỏ trước | `test(backend): upload tests pass with or without ffprobe on the machine (VT-018)` | `5601073` |
| 2 | [x] CI backend cài ffmpeg để chạy đường probe thật; test báo lỗi nếu CI thiếu ffprobe | `ci(backend): run the real ffprobe path in CI (VT-018, BE-15)` | `29635f6` |
| 3 | [x] Histogram `api_admission_wait_seconds`: thời gian request chờ ở hàng đợi admission; test đỏ trước (RE-018, AD-018) | `feat(backend): measure how long requests wait for admission (RE-018, AD-018)` | `b07ed2e` |
| 4 | [x] Harness đọc `/metrics` trước và sau lượt đo: p95 phía server (xử lý, chờ admission) đặt cạnh p95 phía client (AI-19) | `test(backend): load harness reports server-side latency next to client-side (AI-19)` | `3283559` |
| 5 | [x] Harness chia client ra nhiều process để máy sinh tải không thành nút cổ chai; so sánh 1 và nhiều process client trên cùng cấu hình server (AI-19) | `test(backend): load harness can spread clients over several processes (AI-19)` | `495b1a8` |
| 6 | [x] Đo lại 247 trên `main` sau #45: 1 và 4 process API, 3 lần mỗi cấu hình, kèm phần tách client/server (AD-018) | `test(backend): re-measure 247 clients on main after the upload query cut (AD-018, AI-19)` | `eefe800` |
| 7 | [x] Đo lại 239 và 40 trên `main` (hồi quy) (RE-018, VT-018) | `test(backend): re-measure 239 and 40 clients on main (RE-018, VT-018, AI-19)` | `e564a17` |
| 8 | [x] Bảng thời gian phản hồi PR (mở → review đầu tiên → merge) sinh từ GitHub, kèm script; ghi đúng các PR merge không có review (RE-018 20 giờ, AD-018 18 giờ) | `docs(evidence): PR response times from GitHub, with the script (RE-018, AD-018)` | `9f7cf78` |
| 9 | [x] ROADMAP: cột "Hiện trạng" của ba bảng yêu cầu theo code hiện tại (bảng đang ghi theo `53f753b` ngày 11-06) | `docs(tasks): requirement status in the roadmap matches main (G0)` | `e55505f` |
| 10 | [x] Bản đồ bằng chứng, kết quả, hash | `docs(evidence): evidence map and 2026-11-10 member C results (G0)` | commit này |

## Kết quả và điều còn mở

Ngoài 10 commit: `a7ddfee` (giao việc), `7695f24` (sửa việc 5 và 6 của B cho đúng chỗ trùng lặp thật).

- **Test theo môi trường:** 5 test upload đỏ trên máy có ffprobe, xanh trên CI. Sau commit 1 và 2: máy có ffprobe 383 passed, 0 failed; CI cài ffmpeg, 400 passed, 5 test ffprobe thật chạy (không skip).
- **247 client (AD-018):**
  - 1 process API **không đạt**: p95 upload 2,25 đến 3,75 s, 14/14 lượt.
  - 4 process API (`API_MAX_INFLIGHT=20`): đạt ở 10/12 lượt, 1,08 đến 2,18 s, sát mốc khi máy bận (VS Code dùng khoảng 3,7 CPU). **Không** ghi là đạt chắc chắn.
  - #45 giảm p95 khoảng 0,15 s (chạy xen kẽ trước và sau).
  - Máy sinh tải một process có làm số xấu thêm, nhưng phía server cũng không đạt ở 1 process.
- **Lỗi `RemoteProtocolError`:** 6/6.669 upload ở 247 client. Ba lỗi có chi tiết xảy ra khi kết nối đã rảnh 4,94 đến 5,00 s, đúng timeout keep-alive 5 s của uvicorn. Lỗi do harness; thử riêng lẻ 0/42. Đường thật qua nginx không dùng lại kết nối tới uvicorn. Harness chưa sửa, để số vẫn so được với các lần trước.
- **239 client:** 239/239 upload, 0 lỗi, p95 2,09 đến 2,37 s. **40 client:** p95 0,36 đến 0,41 s, đạt.
- **Phản hồi PR:** từ 11-06, 4/15 PR có phản hồi của người khác. #44 được C review sau 22,0 giờ (quá 18 và 20 giờ). 10 PR merge khi chưa có phản hồi, gồm #40 và #43 của C.
- **Còn mở cho 11-11:**
  - Quyết định có sửa harness (đăng nhập ngay trước barrier, hoặc keep-alive dài hơn) hay giữ nguyên để so sánh.
  - Đo lại 247 sau khi B gộp metric nhiều process, để có số phía server cho 4 process.
  - DER vẫn chưa làm (chưa có SH-01).
