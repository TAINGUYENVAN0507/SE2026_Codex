# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 246 | 1.2924 | 1.9245 | 2.0265 |
| poll trạng thái job | 1230 | 0.0153 | 0.0714 | 0.1295 |
| **tất cả** | 1476 | 0.0177 | **1.6389** | 2.0265 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 1 {'create:RemoteProtocolError': 1}. Từ lúc thả client tới khi xong: 12.34 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 8.7183 s, max 18.0631 s; 176/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

Không có số phía server: nhiều process API: /metrics chỉ của một process.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 247 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
