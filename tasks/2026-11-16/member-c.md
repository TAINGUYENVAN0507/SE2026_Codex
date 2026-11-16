# 2026-11-16 · Member C: harness dọn file audio, CPU của event loop ở 247 client, 40 client đổi thứ tự (Đợt 10, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:**
  - **#60 (A):** C review diff. Thay đổi `RemoteSummary.tsx` chỉ là comment. E2E tự chạy worker `summary_fail` với `workers: 1`, nên không có worker khác tranh job. CI xanh 11/11. Merge `544333d`.
  - **#61 (B):** chưa merge. C chạy uvicorn thật và xác nhận P1 của A: access log có `?q=<canary>`. Đọc code xác nhận P2. C thêm điểm số liệu người nói bằng 0. B sửa trên chính #61.
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app. Chỉ thêm test, công cụ đo và bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Harness tải xóa file audio và artifact của các meeting nó tạo sau mỗi lượt. Lấy id từ DB của lượt đó, chỉ nhận UUID; cờ `--keep-audio` để giữ lại. Ghi số thư mục audio lúc bắt đầu và kết thúc vào `summary.json` (`storage_cleanup`). Unit test. Trước nay harness không dọn, `backend/appdata` của máy đo lên 2,3 GB | `test(backend): load harness removes the files of the meetings it created (VT-018, AD-018)` | `95878ba` |
| 2 | [x] Harness ghi CPU của từng process API trong pha upload, tách luồng chính (event loop) khỏi cả process. 247 client, 1, 2 và 4 process API, 3 vòng, thứ tự xoay vòng. Kiểm câu "phần chậm của 1 process nằm trước middleware": nếu event loop của 1 process bận gần 1 CPU thì đó là nghẽn | `test(backend): API event-loop CPU at 247 clients on 1, 2 and 4 processes (AD-018)` | `6f58a11` |
| 3 | [x] 40 client: thư mục lưu đầy và rỗng, **đổi thứ tự giữa các vòng** (đầy trước ở vòng lẻ, rỗng trước ở vòng chẵn). Ngày 11-15 thứ tự cố định nên "thư mục đầy chậm hơn 0,13 s" còn lẫn với thứ tự chạy | `test(backend): 40-client full and empty storage with the run order alternated (VT-018)` | `c7fe477` |
| 4 | [x] Sinh lại thời gian phản hồi PR tới #62. Bản đồ bằng chứng và ROADMAP sau #60 và review #61: log uvicorn và nginx ghi query string, số liệu người nói | `docs(evidence): evidence map, PR response times and roadmap after #60 and the #61 review (RE-018, AD-018, VT-018)` | `fc6dc3f` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-16 member C results (G0)` | commit này |

## Việc chung (không tính commit)

- Review head mới của #61 khi B push, và PR ngày 11-16 của A. Merge #61 trước PR của A, vì việc 2 của A cho giao diện gửi `?q=` lên API.

## Kết quả và điều còn mở

Ngoài 5 commit:
- `a4eab25`: giao việc, PR #62, merge `3ed9c0d` để A và B đọc được trên `main`.
- Trước đó C review và merge #60, và review #61. Hai review là comment trên GitHub.

- **#61 (B):** chưa merge.
  - P1 của A: C chạy uvicorn thật với code của #61, `GET /api/v1/meetings?q=<canary>` ra dòng access log có nguyên canary.
  - P2: đọc code, smoke Compose in cảnh báo rồi báo thành công khi không đọc được log.
  - C thêm `segment_count`, `speaking_time_sec` luôn bằng 0. B sửa cả ba trên chính #61.
- **Harness:**
  - Mỗi lượt xóa đúng file của các meeting nó tạo (5 client: 6 thư mục; 40 client: 43 đến 45; 247 client: 253). Thư mục `full` giữ 22.947 thư mục qua 12 lượt.
  - Mutant bỏ bước kiểm UUID: 6 test đỏ.
  - `summary.md` có thêm kết luận theo p95 upload. Kết luận cũ gộp poll, nên lượt `p1-2` (p95 upload 2,32 s) vẫn PASS.
- **247 client (AD-018):**
  - 1 process: 3/3 trên mốc (2,32 đến 3,24 s). Process uvicorn dùng 1,10 đến 1,15 CPU, gần trần của một process Python có GIL; event loop chỉ được 0,28 đến 0,32 CPU.
  - 2 process: 3/3 đạt (1,50 đến 1,60 s), lần đầu đo.
  - 4 process: 3/3 đạt (1,04 đến 1,39 s).
  - Chưa đo trực tiếp thời gian chờ GIL.
- **40 client (VT-018):**
  - 12/12 đạt (0,38 đến 0,64 s). Thứ tự chạy không phải lý do (0,48 và 0,47 s).
  - Thư mục đầy chậm hơn trung bình 0,08 s, nhưng chỉ ở 4/6 vòng.
  - Gộp 5 ngày: 51/52 lượt đạt.
- **Phản hồi PR:** từ 11-06, 7/31 PR có phản hồi của người khác, 5/7 trong 18 và 20 giờ. Review chéo Đợt 9: A review #61 sau 4,4 giờ, hai điểm đều đúng. B không review #60; phản hồi đầu tiên của #60 là của C sau 20,2 giờ.
- **Bản đồ bằng chứng:** dòng "Log không giữ dữ liệu cá nhân" của AD-018 đổi từ "Có" sang "Một phần" (uvicorn và nginx ghi query string).
- **Backend:** trên Postgres 16, 482 passed, 0 skipped. Ruff sạch. Lượt đầu `test_evidence_map_links` đỏ vì bản đồ ghi `infra/docker/api.Dockerfile:65`; đã sửa trong commit 4 trước khi push.
- **Còn mở:**
  - Mặc định Compose `API_WORKERS: 1` không đạt 247 client. 2 process đạt ở lần đo duy nhất. Đổi mặc định là quyết định cấu hình, cần đo lại trên chính Compose.
  - Nguyên nhân lượt 1,56 s ngày 11-12 (40 client) và ngày 11-11 (247 client, 4 process) vẫn chưa rõ.
  - Thư mục `backend/appdata` của máy đo vẫn còn 22.947 thư mục audio cũ của harness (2,3 GB). Harness không biết thư mục nào là của nó vì DB các lượt trước đã bị tạo lại, nên C không xóa.
