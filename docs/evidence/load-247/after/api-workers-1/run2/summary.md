# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 2.4151 | 4.1362 | 4.1918 |
| poll trạng thái job | 1235 | 0.1315 | 0.8358 | 1.286 |
| **tất cả** | 1482 | 0.1569 | **3.0977** | 4.1918 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 0 . Thời gian toàn bộ: 36.66 s.
Trạng thái meeting khi kết thúc: {'queued': 100}.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
