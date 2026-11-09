# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 97 | 61.4742 | 61.7946 | 61.8145 |
| poll trạng thái job | 485 | 0.0446 | 0.145 | 38.6497 |
| **tất cả** | 582 | 0.0584 | **61.6803** | 61.8145 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 150. Thời gian toàn bộ: 93.79 s.
Trạng thái meeting khi kết thúc: {'queued': 75, 'ready': 22}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
