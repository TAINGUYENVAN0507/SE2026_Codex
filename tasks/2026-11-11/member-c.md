# 2026-11-11 · Member C: harness hết race keep-alive, đo 247 với số phía server khi chạy 4 process (Đợt 6)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #47 và #48 đã vào `main` (C review, gộp thử và chạy test, rồi merge ngày 2026-11-11, `1f9d1ca`).
- **Mục tiêu:**
  1. Hai việc còn mở từ 11-10. Lỗi `RemoteProtocolError` ở 247 client đến từ harness. Đồng thời phía server chưa có số khi chạy 4 process, vì `/metrics` lúc đó chỉ là của một process. #48 đã gộp metric mọi process.
  2. Đo lại 247, 239 và 40 trên `main` sau #47 và #48, vì #48 chuyển upload sang service.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [ ] Harness đóng kết nối rảnh trước khi uvicorn đóng (client `keepalive_expiry` < 5 s); bản repro đỏ trước với 5 s, xanh với giá trị mới (AI-19) | `fix(backend): load harness drops idle connections before uvicorn does (AI-19)` | |
| 2 | [ ] Harness lấy số phía server cả khi chạy nhiều process API (`PROMETHEUS_MULTIPROC_DIR` riêng cho mỗi lượt đo) (AI-19, BE-19) | `test(backend): load harness reads server-side latency with several API processes (AI-19)` | |
| 3 | [ ] Đo lại 247 trên `main`: 1 và 4 process API, 3 lượt mỗi cấu hình, có số phía server cho cả hai (AD-018) | `test(backend): re-measure 247 clients with server-side numbers for 4 processes (AD-018, AI-19)` | |
| 4 | [ ] Đo lại 239 và 40 trên `main` sau #48 (hồi quy) (RE-018, VT-018) | `test(backend): re-measure 239 and 40 clients after the upload service move (RE-018, VT-018, AI-19)` | |
| 5 | [ ] Bản đồ bằng chứng, bảng Tải và Việc treo trong ROADMAP, bảng phản hồi PR, tick và hash (G0) | `docs(evidence): 2026-11-11 load results and member C record (G0)` | |
