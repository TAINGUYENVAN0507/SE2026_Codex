# 247 client trên `main` sau #61 và #64: 1, 2 và 4 process API, log của API đếm dưới tải (AD-018, 2026-11-17)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

Hôm nay `main` có #61 (uvicorn `--no-access-log`, số liệu người nói) và #64 (tìm kiếm qua API, log nginx). Đo lại để xem hai PR đổi kết quả tải không, và kiểm dưới tải rằng stdout của API không có query string.

- **Code:** `main` `1dc6b5c`; `env.json` ghi `bacc9c3` (thêm commit harness đếm log của C, `backend/app` như `1dc6b5c`).
- **Cấu hình:** như [`../event-loop-2026-11-16/README.md`](../event-loop-2026-11-16/README.md): 1 máy 12 CPU, Postgres 16 cục bộ mới khởi tạo, pipeline fake, WAV im lặng 3 s, 4 process sinh tải, không ghim CPU. 4 process dùng `API_MAX_INFLIGHT=20`.
- **Thứ tự:** hình vuông Latin, 3 vòng ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)). 12:44 đến 12:50. Load average lúc bắt đầu lượt 5,7 đến 11,1 (lượt đầu 2,8).
- **Kết luận dùng p95 upload** (`create` trong `summary.json`). Harness chạy `uvicorn --log-level warning`, không có `--no-access-log` vì không có access log của uvicorn ở mức này.

## Kết quả

| Process API | Vòng | p95 upload (s) | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|
| 1 | 1 | 2,29 | 0,27 / 1,10 |
| 1 | 2 | 2,12 | 0,29 / 1,10 |
| 1 | 3 | 2,13 | 0,30 / 1,16 |
| 2 | 1 | 1,41 | 0,24 / 0,99; 0,29 / 1,06 |
| 2 | 2 | 1,38 | 0,29 / 1,04; 0,26 / 1,06 |
| 2 | 3 | 1,40 | 0,25 / 0,96; 0,31 / 1,08 |
| 4 | 1 | 1,11 | 0,24 / 0,77; 0,26 / 0,83; 0,24 / 0,81; 0,26 / 0,85 |
| 4 | 2 | 1,01 | 0,27 / 0,82; 0,30 / 0,93; 0,23 / 0,71; 0,26 / 0,78 |
| 4 | 3 | 1,03 | 0,23 / 0,73; 0,27 / 0,89; 0,23 / 0,73; 0,23 / 0,73 |

0 lỗi ở cả 9 lượt; mỗi lượt 247 upload và 1.235 poll. p95 tính từ `create` trong `summary.json`.

- **1 process: 3/3 trên mốc** (2,12 đến 2,29 s), cùng kiểu 11-16 (2,32 đến 3,24 s). Process vẫn chạm khoảng 1,1 CPU.
- **2 process: 3/3 đạt** (1,38 đến 1,41 s), lần đo thứ hai (11-16: 1,50 đến 1,60 s).
- **4 process: 3/3 đạt** (1,01 đến 1,11 s).
- Hai PR không làm đổi thứ tự cấu hình. Chênh với 11-16 (1 process nhanh hơn 0,2 đến 1 s) nằm trong dao động giữa các ngày đã thấy; load máy khác nhau, không kết luận là cải thiện.

## Log của API dưới tải

Cột mới `api_log` trong `summary.json` (từ `bacc9c3`): harness đưa stdout của API vào file tạm, đếm rồi bỏ.

- Cả 9 lượt: 1.981 dòng, 1.734 dòng access của app (`app.access`), **0 dòng access của uvicorn, 0 dòng có query string**.
- Đây là kiểm trên uvicorn thật dưới 247 client, bổ sung cho test của B (`backend/tests/privacy/test_privacy_access_log.py`). Harness không gọi `?q=`, nên kiểm này cho thấy log tải không có query string, không thay cho test của B.

## Giới hạn

- Như 11-16: một máy, pipeline fake, Postgres chung máy, 3 lượt mỗi cấu hình trong khoảng 6 phút.
- Compose vẫn đặt `API_WORKERS: 1` (`docker-compose.yml:36`), không đạt mốc ở cấu hình này. Đổi mặc định chưa làm, cần đo trên chính Compose.
- Harness chạy `uvicorn` trực tiếp, không qua Docker: log của container (json-file, xoay vòng 10 MB × 3 của #61) chưa đo.
