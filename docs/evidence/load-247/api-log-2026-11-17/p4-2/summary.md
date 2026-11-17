# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 0.7111 | 1.0078 | 1.0647 |
| poll trạng thái job | 1235 | 0.0079 | 0.0525 | 0.0956 |
| **tất cả** | 1482 | 0.0097 | **0.837** | 1.0647 |

Mục tiêu p95 ≤ 2.0 s: upload **PASS** (p95 upload 1.0078 s); mọi request gộp upload và poll **PASS** (exit code theo số này). Lỗi: 0 . Từ lúc thả client tới khi xong: 11.26 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Máy sinh tải dùng trung bình 0.73 CPU trong pha upload (được dùng 12). Ghim CPU: server không, client không.

CPU phía server trong pha upload (1.08 s), process dùng ≥ 0,05 CPU: api python cấp 2: luồng chính 0.27, cả process 0.82; api python cấp 2: luồng chính 0.3, cả process 0.93; api python cấp 2: luồng chính 0.23, cả process 0.71; api python cấp 2: luồng chính 0.26, cả process 0.78.

Stdout của API: 1981 dòng, trong đó 1734 dòng access của app, 0 dòng access của uvicorn; dòng có query string: **0**.

Thư mục lưu `appdata/audio` có 22950 thư mục lúc bắt đầu, 22950 lúc kết thúc (đã xóa 251 thư mục audio và artifact của 247 meeting lượt này tạo).
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 4.8486 s, max 9.5762 s; 119/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 247 | 0.6397 | 0.5 – 0.75 | 0.75 – 1.0 | 1.0 | 1.0 |
| poll, tổng thời gian ở app | 1235 | 0.0113 | 0.005 – 0.01 | 0.025 – 0.05 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 1482 | 0.0581 | 0.0 – 0.001 | 0.5 – 0.75 | 1.0 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 1.0, ≤ 2,0 s = 1.0.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 247/247, poll 1235/1235 (4 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
