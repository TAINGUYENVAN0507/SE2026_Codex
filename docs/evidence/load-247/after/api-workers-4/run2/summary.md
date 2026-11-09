# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.6558 | 2.4271 | 2.4967 |
| poll trạng thái job | 1235 | 0.011 | 0.0359 | 0.1634 |
| **tất cả** | 1482 | 0.013 | **1.8449** | 2.4967 |

Mục tiêu p95 ≤ 2.0 s: **PASS**. Lỗi: 0 . Thời gian toàn bộ: 33.51 s.
Trạng thái meeting khi kết thúc: {'queued': 100}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
