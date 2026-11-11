# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.7647 | 2.3171 | 2.3825 |
| poll trạng thái job | 1235 | 0.0077 | 0.0214 | 0.0748 |
| **tất cả** | 1482 | 0.0091 | **1.8329** | 2.3825 |

Mục tiêu p95 ≤ 2.0 s: **PASS**. Lỗi: 0 . Từ lúc thả client tới khi xong: 12.57 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 4.7413 s, max 9.48 s; 117/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 247 | 1.4843 | 1.5 – 2.0 | 2.0 – 2.5 | 0.4494 | 0.8178 |
| poll, tổng thời gian ở app | 1235 | 0.0079 | 0.005 – 0.01 | 0.01 – 0.025 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1482 | 0.1371 | 0.0 – 0.001 | 1.0 – 1.5 | 0.9622 | 0.9966 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.4372, ≤ 2,0 s = 0.7976.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 247/247, poll 1235/1235 (4 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
