# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 246 | 2.0296 | 3.2992 | 3.6239 |
| poll trạng thái job | 1230 | 0.1024 | 0.6032 | 1.061 |
| **tất cả** | 1476 | 0.1473 | **2.7057** | 3.6239 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 1 {'create:RemoteProtocolError': 1}. Từ lúc thả client tới khi xong: 14.38 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 8.925 s, max 18.5392 s; 178/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 246 | 1.7012 | 1.5 – 2.0 | 2.5 – 3.0 | 0.374 | 0.5894 |
| poll, tổng thời gian ở app | 1230 | 0.143 | 0.05 – 0.1 | 0.5 – 0.75 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1476 | 0.2324 | 0.0 – 0.001 | 1.5 – 2.0 | 0.9302 | 0.9804 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.3374, ≤ 2,0 s = 0.4959.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 247 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
