# 2026-11-15 · Member C: chặn bằng chứng không phải UTF-8, hai nghi vấn còn lại ở 40 client, 247 client tách CPU (Đợt 9, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #56 (B) và #57 (A) đã vào `main`. C review diff, gộp thử cả hai, backend 444 passed / 16 skipped (không có Postgres); #56 CI xanh 15/15; #57 chỉ đổi docs nên CI không chạy, C kiểm mọi link tương đối trong file đổi: 0 hỏng. Merge `1e71c89`, `115c905`.
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app. Chỉ thêm test, công cụ đo và bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [ ] Test chặn file văn bản trong `docs/`, `tasks/`, `reports/` không phải UTF-8 hoặc có BOM UTF-16. Khi review #56 thấy `docs/evidence/final/summary-partial-red-2026-11-13.log` là UTF-16, lần thứ hai sau `deletion-2026-11-12.log` (#54). Test đỏ trước trên `main`, rồi đổi file đó sang UTF-8, nội dung giữ nguyên | `test(docs): evidence and task files must be UTF-8 (G0)` | |
| 2 | [ ] 40 client: kiểm hai nghi vấn còn lại của mức chậm ngày 11-12, xen kẽ `base` / `nosync` (Postgres `synchronous_commit=off` qua tham số kết nối) / `tmpfs` (thư mục audio trên `/dev/shm`) | `test(backend): 40-client runs isolating commit fsync and audio writes (VT-018)` | |
| 3 | [ ] 247 client: thêm `--server-cpus` và `--client-cpus` vào harness, có unit test; đo xen kẽ chung CPU / tách CPU ở 1 và 4 process API. Kiểm câu "phần chênh nằm trước middleware và ở máy sinh tải" của ngày 11-11 | `test(backend): 247 clients with the load generator on separate cores (AD-018, AI-19)` | |
| 4 | [ ] Sinh lại thời gian phản hồi PR tới #57; bản đồ bằng chứng và ROADMAP theo `main` sau #56, #57 | `docs(evidence): evidence map, PR response times and roadmap after #56, #57 (RE-018, AD-018, VT-018)` | |
| 5 | [ ] Tick, hash | `docs(tasks): record 2026-11-15 member C results (G0)` | commit này |

## Kết quả và điều còn mở

(điền khi xong)
