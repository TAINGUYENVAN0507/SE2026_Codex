# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 246 | 2.1559 | 3.5441 | 3.896 |
| poll trạng thái job | 1230 | 0.122 | 0.6692 | 1.1736 |
| **tất cả** | 1476 | 0.2008 | **2.8043** | 3.896 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 1 {'create:RemoteProtocolError': 1}. Từ lúc thả client tới khi xong: 14.49 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 8.9868 s, max 18.6719 s; 178/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 246 | 1.9338 | 2.0 – 2.5 | 2.5 – 3.0 | 0.3293 | 0.4959 |
| poll, tổng thời gian ở app | 1230 | 0.1678 | 0.1 – 0.25 | 0.5 – 0.75 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1476 | 0.2833 | 0.0 – 0.001 | 2.0 – 2.5 | 0.916 | 0.9458 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.3171, ≤ 2,0 s = 0.4472.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 247 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
