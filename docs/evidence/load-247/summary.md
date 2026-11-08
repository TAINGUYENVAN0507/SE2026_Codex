# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 91 | 62.8939 | 63.3864 | 63.404 |
| poll trạng thái job | 455 | 0.1104 | 0.4266 | 29.4117 |
| **tất cả** | 546 | 0.1464 | **63.2505** | 63.404 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 155. Thời gian toàn bộ: 98.29 s.
Trạng thái meeting khi kết thúc: {'queued': 75, 'ready': 16}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
