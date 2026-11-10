# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 2.2029 | 3.7485 | 3.8939 |
| poll trạng thái job | 1235 | 0.1246 | 0.6922 | 1.2271 |
| **tất cả** | 1482 | 0.191 | **2.9266** | 3.8939 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 0 . Từ lúc thả client tới khi xong: 14.76 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 9.0836 s, max 17.9384 s; 178/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 247 | 1.9569 | 2.0 – 2.5 | 2.5 – 3.0 | 0.3239 | 0.4818 |
| poll, tổng thời gian ở app | 1235 | 0.1765 | 0.1 – 0.25 | 0.5 – 0.75 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1482 | 0.2854 | 0.0 – 0.001 | 1.5 – 2.0 | 0.9143 | 0.9595 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.2551, ≤ 2,0 s = 0.3927.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 247 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
