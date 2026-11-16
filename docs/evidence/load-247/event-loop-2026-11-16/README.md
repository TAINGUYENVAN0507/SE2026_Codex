# 247 client: CPU của từng process API trong pha upload (AD-018, 2026-11-16)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

Ngày 11-15, 1 process API (mặc định, `docker-compose.yml:31` đặt `API_WORKERS: 1`) không đạt ở 6/6 lượt. Phía server, phần lớn upload xong trong 2,0 s, phía client thì không. Đã loại máy sinh tải ([`../pinned-2026-11-15/README.md`](../pinned-2026-11-15/README.md)). Phần còn lại được ghi là "uvicorn một event loop nhận 247 kết nối, chưa đo riêng". Hôm nay đo phần đó: event loop có bị nghẽn không.

- **Code:** app là `main` `3ed9c0d` (sau #60, #62; `backend/app` như `115c905`). `env.json` ghi `95878ba`, là commit harness dọn file của C ngay trước. Phần đo CPU phía server của harness lúc chạy chưa commit; commit cùng thư mục này mà không sửa thêm.
- **Môi trường:** 1 máy 12 CPU (6 nhân × 2 luồng), Python 3.12 (có GIL), uvicorn với `uvloop` và `httptools`. Postgres 16 cục bộ, cluster mới khởi tạo hôm nay, `max_connections=100`, `ssl=off`, TCP `127.0.0.1`. 1 worker, pipeline fake, WAV im lặng 3 s, 4 process sinh tải, không ghim CPU.
- **Ngân sách kết nối:** 4 process dùng `API_MAX_INFLIGHT=20` như các ngày trước; 1 và 2 process dùng mặc định 40.
- **Ba cấu hình, 3 vòng, thứ tự xoay vòng** (vòng 1: 1, 2, 4 process; vòng 2: 2, 4, 1; vòng 3: 4, 1, 2), để thứ tự chạy không trùng với cấu hình. Nghỉ 15 s giữa các lượt ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)). Tên lượt là `p<số process>-<vòng>`.
- **Kết luận dùng p95 của upload** (`POST /meetings`, tính từ `raw.csv`), như các ngày trước. `exit` trong `run-log.txt` và dòng `PASS`/`FAIL` trong `summary.md` tính p95 trên mọi request, gồm cả 1.235 poll nhanh, nên không dùng để kết luận. Ví dụ `p1-2`: p95 upload 2,32 s (trên mốc) nhưng `exit=0`. Từ commit sau, harness ghi thêm kết luận riêng cho upload.
- **Cách đo CPU phía server** (`summary.json`, khóa `server_cpu`):
  - Harness đọc `/proc/<pid>/stat` (cả process, mọi luồng) và `/proc/<pid>/task/<pid>/stat` (riêng luồng chính) của mọi process trong cây API.
  - Đọc hai lần: lúc thả client, và lúc upload cuối xong. Hiệu chia cho thời gian giữa hai lần là số CPU trung bình.
  - Với uvicorn, luồng chính chạy event loop. Endpoint `def` của FastAPI chạy ở threadpool, tức các luồng khác của cùng process.
  - Unit test: `backend/tests/unit/test_load_harness.py` (process bận ở luồng chính, process con bận ở luồng phụ).
- Mỗi lượt có `summary.json`, `summary.md`, `raw.csv`, `env.json`. Stdout từng lượt không giữ.
- Lúc đo: 12:20 đến 12:28. Load average lúc bắt đầu lượt từ 1,2 (lượt đầu) đến 15,6.

## Kết quả

"Pha upload" tính từ lúc thả client tới lúc upload cuối xong. CPU là số trung bình trong pha đó: "luồng chính / cả process", mỗi process API một cặp. Process giám sát của uvicorn (khi chạy 2 hoặc 4 process) và worker dùng ≤ 0,02 CPU nên không ghi.

| Process API | Vòng | p95 upload (s) | ≤ 2,0 s: client / server | Pha upload (s) | CPU từng process API | CPU sinh tải |
|---|---|---|---|---|---|---|
| 1 | 1 | 3,24 | 57,5 % / 78,1 % | 3,31 | 0,29 / 1,10 | 0,26 |
| 1 | 2 | 2,32 | 72,5 % / 100,0 % | 2,46 | 0,32 / 1,14 | 0,42 |
| 1 | 3 | 3,03 | 49,8 % / 66,0 % | 3,26 | 0,28 / 1,15 | 0,27 |
| 2 | 1 | 1,50 | 100,0 % / 100,0 % | 1,61 | 0,26 / 1,06; 0,26 / 1,01 | 0,45 |
| 2 | 2 | 1,54 | 100,0 % / 100,0 % | 1,64 | 0,24 / 0,96; 0,26 / 1,07 | 0,45 |
| 2 | 3 | 1,60 | 100,0 % / 100,0 % | 1,70 | 0,23 / 0,94; 0,25 / 1,00 | 0,45 |
| 4 | 1 | 1,39 | 100,0 % / 100,0 % | 1,46 | 0,19 / 0,54; 0,23 / 0,79; 0,17 / 0,56; 0,18 / 0,58 | 0,56 |
| 4 | 2 | 1,26 | 100,0 % / 100,0 % | 1,35 | 0,23 / 0,76; 0,27 / 0,90; 0,24 / 0,76; 0,26 / 0,84 | 0,61 |
| 4 | 3 | 1,04 | 100,0 % / 100,0 % | 1,16 | 0,26 / 0,87; 0,24 / 0,77; 0,25 / 0,79; 0,23 / 0,77 | 0,70 |

p95 tính từ `raw.csv` (quantile theo hạng gần nhất). 0 lỗi ở cả 9 lượt (2.223 upload). Server đếm 247/247 upload và 1.235/1.235 poll ở mọi lượt.

- **1 process API: không đạt, 3/3 lượt trên mốc** (2,32 đến 3,24 s), như 11-15 (2,09 đến 2,75 s).
- **Event loop không bận hết, cả process thì có.** Trong pha upload, process uvicorn dùng 1,10 đến 1,15 CPU. Đây là khoảng mức một process Python 3.12 có GIL dùng được: mã Python của mọi luồng thay nhau chạy, chỉ phần C nhả GIL mới chạy song song. Trong số đó, luồng chính (event loop: nhận kết nối, đọc request, chạy middleware) chỉ được 0,28 đến 0,32 CPU; phần còn lại thuộc các luồng threadpool chạy endpoint `def`.
  - Câu "phần chậm nằm trước middleware" của 11-15 vì vậy rõ hơn. Request mới phải chờ event loop, mà event loop phải chờ tới lượt dùng 1 CPU chung của process; nó không bị một việc nào trong chính nó chặn.
  - **Chưa đo trực tiếp thời gian chờ GIL.** Số CPU chỉ cho thấy process chạm trần, chưa chứng minh từng request chờ ở đâu.
- **2 process API: đạt, 3/3 lượt** (1,50 đến 1,60 s). Mỗi process vẫn ở khoảng 1,0 CPU, tức cũng chạm trần, nhưng tổng gấp đôi. Đây là cấu hình chưa đo trước hôm nay. Nó chạy với `API_MAX_INFLIGHT` mặc định 40 (2 × 40 + dự phòng ≤ 100 kết nối Postgres).
- **4 process API: đạt, 3/3 lượt** (1,04 đến 1,39 s). Mỗi process 0,54 đến 0,90 CPU, dưới trần, nên ở 4 process giới hạn đã nằm ở chỗ khác (chưa đo: Postgres, ổ đĩa). Từ 2 lên 4 process, p95 trung bình giảm 0,32 s (1,55 xuống 1,23 s).
- Máy sinh tải dùng 0,26 đến 0,70 CPU trên 12, như 11-15.

## Kết luận cho AD-018

| Cấu hình | 11-10 | 11-11 | 11-15 | 11-16 | Ghi |
|---|---|---|---|---|---|
| 1 process API (mặc định, `docker-compose.yml:31`) | 14/14 trên mốc | 3/3 trên mốc | 6/6 trên mốc | 3/3 trên mốc | **Không đạt.** Process chạm trần khoảng 1 CPU |
| 2 process API | chưa đo | chưa đo | chưa đo | 3/3 đạt (1,50 đến 1,60 s) | **Đạt ở một ngày**, sát mốc hơn 4 process |
| 4 process API, `API_MAX_INFLIGHT=20` | 10/12 đạt | 0/15 đạt | 9/9 đạt | 3/3 đạt (1,04 đến 1,39 s) | Đạt ở 11-10, 11-15, 11-16; không đạt ở 11-11, nguyên nhân chưa rõ |

Cấu hình mặc định (Compose đặt `API_WORKERS: 1`) **không đạt AD-018**. Đổi mặc định sang 2 hoặc 4 process là đổi cấu hình triển khai, chưa làm trong đợt này. Muốn đổi thì cần đo lại trên chính Compose.

## Giới hạn

- Một máy, pipeline fake, client là thread Python, Postgres chung máy, như các ngày trước. Mỗi cấu hình 3 lượt trong khoảng 8 phút, cùng một trạng thái máy.
- `server_cpu` không có Postgres, vì Postgres chạy ngoài harness.
- Số CPU lấy từ tick của `/proc` (`CLK_TCK` = 100, tức 10 ms), trên pha upload dài 1,2 đến 3,3 s, nên sai số khoảng ±0,02 CPU mỗi số.
- Harness chạy uvicorn với `--log-level warning`, nên không có access log của uvicorn. Compose chạy với log mặc định có access log, mỗi request thêm một dòng ra stdout. Phần đó chưa đo.
