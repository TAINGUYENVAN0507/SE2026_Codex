# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.0113 | 1.4068 | 1.4746 |
| poll trạng thái job | 1235 | 0.0116 | 0.084 | 0.172 |
| **tất cả** | 1482 | 0.015 | **1.2721** | 1.4746 |

Mục tiêu p95 ≤ 2.0 s: **PASS**. Lỗi: 0 . Từ lúc thả client tới khi xong: 11.78 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

Không có số phía server: nhiều process API: /metrics chỉ của một process.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
