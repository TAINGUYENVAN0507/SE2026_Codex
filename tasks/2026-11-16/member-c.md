# 2026-11-16 · Member C: harness dọn file audio, CPU của event loop ở 247 client, 40 client đổi thứ tự (Đợt 10, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:**
  - **#60 (A):** C review diff. Thay đổi `RemoteSummary.tsx` chỉ là comment. E2E tự chạy worker `summary_fail` với `workers: 1`, nên không có worker khác tranh job. CI xanh 11/11. Merge `544333d`.
  - **#61 (B):** chưa merge. C chạy uvicorn thật và xác nhận P1 của A: access log có `?q=<canary>`. Đọc code xác nhận P2. C thêm điểm số liệu người nói bằng 0. B sửa trên chính #61.
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app. Chỉ thêm test, công cụ đo và bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [ ] Harness tải xóa file audio và artifact của các meeting nó tạo sau mỗi lượt. Lấy id từ DB của lượt đó, chỉ nhận UUID; cờ `--keep-audio` để giữ lại. Ghi số thư mục audio lúc bắt đầu vào `env.json`. Unit test. Trước nay harness không dọn, `backend/appdata` của máy đo lên 2,3 GB | `test(backend): load harness removes the files of the meetings it created (VT-018, AD-018)` | |
| 2 | [ ] Harness ghi CPU của từng process API trong pha upload, tách luồng chính (event loop) khỏi cả process. 247 client, 1 và 4 process API, xen kẽ 3 vòng. Kiểm câu "phần chậm của 1 process nằm trước middleware": nếu event loop của 1 process bận gần 1 CPU thì đó là nghẽn | `test(backend): API event-loop CPU at 247 clients on 1 and 4 processes (AD-018)` | |
| 3 | [ ] 40 client: thư mục lưu đầy và rỗng, **đổi thứ tự giữa các vòng** (đầy trước ở vòng lẻ, rỗng trước ở vòng chẵn). Ngày 11-15 thứ tự cố định nên "thư mục đầy chậm hơn 0,13 s" còn lẫn với thứ tự chạy | `test(backend): 40-client full and empty storage with the run order alternated (VT-018)` | |
| 4 | [ ] Sinh lại thời gian phản hồi PR tới #61. Bản đồ bằng chứng và ROADMAP sau #60 và review #61: log uvicorn và nginx ghi query string, số liệu người nói | `docs(evidence): evidence map, PR response times and roadmap after #60 and the #61 review (RE-018, AD-018, VT-018)` | |
| 5 | [ ] Tick, hash | `docs(tasks): record 2026-11-16 member C results (G0)` | |

## Việc chung (không tính commit)

- Review head mới của #61 khi B push, và PR ngày 11-16 của A. Merge #61 trước PR của A, vì việc 2 của A cho giao diện gửi `?q=` lên API.
