# Kết quả tải VT-018 (239 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 1 | 91.4911 | 91.4911 | 91.4911 |
| poll trạng thái job | 5 | 0.0127 | 88.5971 | 88.5971 |
| **tất cả** | 6 | 0.0136 | **91.4911** | 91.4911 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 101. Thời gian toàn bộ: 208.42 s.
Trạng thái meeting khi kết thúc: {'queued': 39, 'ready': 4}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
