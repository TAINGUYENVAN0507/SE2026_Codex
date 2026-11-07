# Kết quả tải VT-018 (40 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 40 | 0.637 | 0.7107 | 0.7141 |
| poll trạng thái job | 200 | 0.0159 | 0.0666 | 0.0953 |
| **tất cả** | 240 | 0.0209 | **0.6685** | 0.7141 |

Mục tiêu p95 ≤ 1.5 s: **PASS**. Lỗi: 0. Thời gian toàn bộ: 14.5 s.
Trạng thái meeting khi kết thúc: {'queued': 37, 'ready': 3}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
