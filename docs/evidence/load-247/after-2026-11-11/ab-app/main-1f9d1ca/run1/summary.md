# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.9033 | 2.5976 | 2.637 |
| poll trạng thái job | 1235 | 0.0092 | 0.0938 | 0.1833 |
| **tất cả** | 1482 | 0.0122 | **2.1245** | 2.637 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 0 . Từ lúc thả client tới khi xong: 12.82 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 4.7768 s, max 9.3996 s; 116/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 247 | 1.712 | 1.5 – 2.0 | 2.5 – 3.0 | 0.3725 | 0.6559 |
| poll, tổng thời gian ở app | 1235 | 0.0173 | 0.005 – 0.01 | 0.05 – 0.1 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1482 | 0.158 | 0.0 – 0.001 | 1.5 – 2.0 | 0.9494 | 0.9926 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.3644, ≤ 2,0 s = 0.5911.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 247/247, poll 1235/1235 (4 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
