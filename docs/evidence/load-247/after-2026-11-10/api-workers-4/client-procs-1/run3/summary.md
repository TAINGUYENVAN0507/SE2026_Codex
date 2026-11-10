# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 246 | 0.783 | 1.2034 | 1.3473 |
| poll trạng thái job | 1230 | 0.0122 | 0.0582 | 0.114 |
| **tất cả** | 1476 | 0.0154 | **0.9449** | 1.3473 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 1 {'create:RemoteProtocolError': 1}. Từ lúc thả client tới khi xong: 11.55 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 100}.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

Không có số phía server: nhiều process API: /metrics chỉ của một process.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 247 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
