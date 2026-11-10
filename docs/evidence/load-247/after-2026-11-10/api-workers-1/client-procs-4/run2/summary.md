# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.515 | 2.8966 | 2.9679 |
| poll trạng thái job | 1235 | 0.0552 | 0.2572 | 0.506 |
| **tất cả** | 1482 | 0.0786 | **2.1757** | 2.9679 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 0 . Từ lúc thả client tới khi xong: 13.55 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 247 | 1.4072 | 1.0 – 1.5 | 2.5 – 3.0 | 0.5992 | 0.7652 |
| poll, tổng thời gian ở app | 1235 | 0.0816 | 0.05 – 0.1 | 0.1 – 0.25 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1482 | 0.1743 | 0.0 – 0.001 | 1.0 – 1.5 | 0.9602 | 0.9879 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.4939, ≤ 2,0 s = 0.6559.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
