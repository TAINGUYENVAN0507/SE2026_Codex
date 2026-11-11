# 2026-11-11 · Member C: harness hết race keep-alive, đo 247 với số phía server khi chạy 4 process (Đợt 6)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #47 và #48 đã vào `main` (C review, gộp thử và chạy test, rồi merge ngày 2026-11-11, `1f9d1ca`).
- **Mục tiêu:**
  1. Hai việc còn mở từ 11-10. Lỗi `RemoteProtocolError` ở 247 client đến từ harness. Đồng thời phía server chưa có số khi chạy 4 process, vì `/metrics` lúc đó chỉ là của một process. #48 đã gộp metric mọi process.
  2. Đo lại 247, 239 và 40 trên `main` sau #47 và #48, vì #48 chuyển upload sang service.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Harness đóng kết nối rảnh trước khi uvicorn đóng (client `keepalive_expiry` < 5 s); test giữ điều kiện đỏ trước với 5 s, xanh với 1 s; race không tái hiện riêng lẻ được nên không có repro đỏ (AI-19) | `fix(backend): load harness drops idle connections before uvicorn does (AI-19)` | `10d991a` |
| 2 | [x] Harness lấy số phía server cả khi chạy nhiều process API (`PROMETHEUS_MULTIPROC_DIR` riêng cho mỗi lượt đo) (AI-19, BE-19) | `test(backend): load harness reads server-side latency with several API processes (AI-19)` | `393c934` |
| 3 | [x] Đo lại 247 trên `main`: 1 và 4 process API, 3 lượt mỗi cấu hình, có số phía server cho cả hai (AD-018) | `test(backend): re-measure 247 clients with server-side numbers for 4 processes (AD-018, AI-19)` | `527938c` |
| 4 | [x] Đo lại 239 và 40 trên `main` sau #48 (hồi quy) (RE-018, VT-018) | `test(backend): re-measure 239 and 40 clients after the upload service move (RE-018, VT-018, AI-19)` | `e3ecee2` |
| 5 | [x] Bản đồ bằng chứng, bảng Tải và Việc treo trong ROADMAP, bảng phản hồi PR, tick và hash (G0) | `docs(evidence): 2026-11-11 load results and member C record (G0)` | commit này |

## Kết quả và điều còn mở

Ngoài 5 commit: `82c905f` (giao việc). Trước khi merge #47 và #48, C gộp thử cả hai và chạy test: backend 393 passed / 14 skipped, frontend 284/284, lines 86,53 %, branches 81,11 %.

- **Harness:** client đóng kết nối rảnh sau 1 s; test giữ điều kiện, log đỏ với 5,0 s. Có số phía server khi chạy nhiều process. Server đếm đúng 247/247 upload với 4 process; trước #48 chỉ đếm được 54 đến 84/247.
- **247 client (AD-018): không đạt.**
  - 1 process: p95 upload 3,16 đến 3,79 s.
  - 4 process: 2,30 đến 2,60 s, 15/15 lượt trên mốc. Kết quả 10/12 lượt đạt của ngày 11-10 không lặp lại được: bản trước #48 chạy xen kẽ hôm nay cũng ra 2,31 đến 2,37 s.
  - Phía server 4 process chỉ 71 đến 82 % upload ≤ 2,0 s, nên thời gian nằm trong app.
  - A/B harness: ba biến thể chồng nhau. A/B app: trước #48 so với `main` chênh +0,24, +0,11 và −0,00 s, chưa đủ để gọi là hồi quy.
- **Lỗi:** 0 ở 21 lượt 247 client (5.187 upload). Harness cũ cũng ra 0 ở 6 lượt hôm nay, nên chưa chứng minh được là hết lỗi.
- **239 client:** 239/239, 0 lỗi, p95 3,03 đến 3,25 s. **40 client:** `main` 0,56 đến 0,84 s ở 6/6 lượt, đạt. Một lượt bản trước #48 lên 1,80 s khi máy bận.
- **Phản hồi PR** (sinh lại): từ 11-06, 5/17 PR có phản hồi của người khác, 4/5 trong 18 và 20 giờ. #47 và #48 merge khi chưa có phản hồi.
- **Còn mở:**
  - AD-018 247 vẫn ✗. Ngày 11-12 đóng băng code, nên chỉ đổi được nếu có sửa lỗi nhỏ làm giảm thời gian xử lý upload.
  - DER vẫn chưa làm (chưa có SH-01).
