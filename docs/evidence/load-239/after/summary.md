# Kết quả tải VT-018 (239 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 239 | 2.5645 | 4.36 | 4.3998 |
| poll trạng thái job | 1195 | 0.1119 | 1.0479 | 1.6133 |
| **tất cả** | 1434 | 0.1348 | **3.729** | 4.3998 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 0 . Thời gian toàn bộ: 35.74 s.
Trạng thái meeting khi kết thúc: {'queued': 100}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
