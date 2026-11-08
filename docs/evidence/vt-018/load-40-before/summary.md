# Kết quả tải VT-018 (40 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 40 | 1.2812 | 1.2865 | 1.2874 |
| poll trạng thái job | 190 | 0.0951 | 0.8707 | 0.9322 |
| **tất cả** | 230 | 0.1157 | **1.2833** | 1.2874 |

Mục tiêu p95 ≤ 1.5 s: **FAIL**. Lỗi: 10. Thời gian toàn bộ: 16.78 s.
Trạng thái meeting khi kết thúc: {'queued': 36, 'ready': 4}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
