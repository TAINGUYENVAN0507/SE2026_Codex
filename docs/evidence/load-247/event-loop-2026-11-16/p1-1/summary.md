# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.5543 | 3.2409 | 3.2854 |
| poll trạng thái job | 1235 | 0.0645 | 0.6097 | 0.8904 |
| **tất cả** | 1482 | 0.1108 | **2.4365** | 3.2854 |

Mục tiêu p95 ≤ 2.0 s: **FAIL**. Lỗi: 0 . Từ lúc thả client tới khi xong: 13.87 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Máy sinh tải dùng trung bình 0.26 CPU trong pha upload (được dùng 12). Ghim CPU: server không, client không.

CPU phía server trong pha upload (3.31 s), process dùng ≥ 0,05 CPU: api uvicorn cấp 1: luồng chính 0.29, cả process 1.1.

Thư mục lưu `appdata/audio` có 22947 thư mục lúc bắt đầu, 22947 lúc kết thúc (đã xóa 253 thư mục audio và artifact của 247 meeting lượt này tạo).
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 5.3729 s, max 10.8331 s; 133/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 247 | 1.2556 | 1.0 – 1.5 | 2.0 – 2.5 | 0.5749 | 0.7814 |
| poll, tổng thời gian ở app | 1235 | 0.0947 | 0.05 – 0.1 | 0.5 – 0.75 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1482 | 0.16 | 0.0 – 0.001 | 0.75 – 1.0 | 0.9561 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.4858, ≤ 2,0 s = 0.5749.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 247/247, poll 1235/1235 (1 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
