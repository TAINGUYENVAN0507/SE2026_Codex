# Kết quả tải VT-018 (40 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 40 | 0.7674 | 0.785 | 0.7924 |
| poll trạng thái job | 200 | 0.0245 | 0.318 | 0.3587 |
| **tất cả** | 240 | 0.0302 | **0.7763** | 0.7924 |

Mục tiêu p95 ≤ 1.5 s: **PASS**. Lỗi: 0 . Từ lúc thả client tới khi xong: 11.37 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 37, 'ready': 3}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 1.1102 s, max 2.2878 s; 0/40 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 40 | 0.7375 | 0.5 – 0.75 | 0.75 – 1.0 | 1.0 | 1.0 |
| poll, tổng thời gian ở app | 200 | 0.0488 | 0.01 – 0.025 | 0.1 – 0.25 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 240 | 0.0 | 0.0 – 0.001 | 0.0 – 0.001 | 1.0 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 1.0, ≤ 2,0 s = 1.0.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 40/40, poll 200/200 (1 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 40 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
