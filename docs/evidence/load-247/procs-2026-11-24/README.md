# 247 client có tìm kiếm, 1 và 4 process API xen kẽ, thư mục lưu trống, trên `main` sau #71 và #72 (AD-018, 2026-11-24)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

Ngày 11-23 đã đo 2 process với thư mục lưu trống ([`../search-ab-2026-11-23/README.md`](../search-ab-2026-11-23/README.md)). Hôm nay đo hai cấu hình còn lại trong cùng điều kiện đó. Mục đích là xem thư mục lưu trống có làm 1 process (mặc định của Compose) đạt mốc không.

- **Code:** `main` `b35e06f`; `env.json` ghi `a6b0992`, tức `main` cộng commit test giới hạn trường của C. `backend/app` như `b35e06f`.
- **Cấu hình:** 4 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s, Postgres 16 cục bộ mới khởi tạo, một máy 12 CPU, không ghim CPU. Thêm `--search 4` và `--storage temp`. 4 process API dùng `API_MAX_INFLIGHT=20`.
- **Thứ tự:** 1 4 4 1 1 4, nghỉ 30 s ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), từ 17:57 đến 18:03. Load average lúc bắt đầu lượt 2,0 đến 9,3.
- **Kết luận dùng p95 upload** (`create` trong `summary.json`).

## Kết quả

| Lượt | Process API | p95 upload (s) | p95 tìm kiếm (s) | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|---|
| p1-1 | 1 | 3,00 | 1,72 | 0,32 / 1,15 |
| p4-2 | 4 | 1,37 | 1,01 | 0,35 / 0,96; 0,32 / 0,96; 0,34 / 0,96; 0,31 / 0,98 |
| p4-3 | 4 | 1,34 | 0,75 | 0,33 / 0,93; 0,30 / 0,92; 0,28 / 0,90; 0,31 / 0,89 |
| p1-4 | 1 | 2,83 | 1,62 | 0,37 / 1,17 |
| p1-5 | 1 | 2,68 | 1,60 | 0,36 / 1,17 |
| p4-6 | 4 | 1,28 | 0,76 | 0,31 / 0,93; 0,35 / 0,93; 0,35 / 0,93; 0,30 / 0,95 |

Cả 6 lượt: 0 lỗi, 0 kết quả tìm sai trong 5.928 lượt tìm, 0 dòng có query string trong stdout của API. Thư mục lưu kết thúc ở 0 thư mục sau mỗi lượt.

- **1 process: 3/3 trên mốc** (2,68 đến 3,00 s). Process vẫn chạm trần khoảng 1,15 CPU. Thư mục lưu trống không làm cấu hình mặc định đạt: ngày 11-19, với thư mục đầy và có tìm kiếm, số đo là 2,28 đến 3,02 s.
- **4 process: 3/3 đạt** (1,28 đến 1,37 s). Ngày 11-19 (thư mục đầy, có tìm kiếm): 1,10 đến 1,15 s. Hôm nay chậm hơn khoảng 0,2 s dù thư mục lưu trống. Chênh này nằm trong dao động giữa các ngày đã thấy (11-16: 1,04 đến 1,39 s), không kết luận được gì.

## Giới hạn

- Một máy, pipeline fake, Postgres chung máy. Mỗi cấu hình 3 lượt.
- `GET /meetings` vẫn có N+1 (giao B, chuyển từ 11-23 sang 11-24). Sau khi B sửa thì đo lại.
- Compose vẫn đặt `API_WORKERS: 1`.
