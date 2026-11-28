# Kết quả tải VT-018 (40 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 40 | 0.6935 | 0.7307 | 0.7359 |
| poll trạng thái job | 200 | 0.0343 | 0.1251 | 0.1491 |
| tìm kiếm `?q=` | 160 | 0.2861 | 0.3953 | 0.4536 |
| **tất cả** | 240 | 0.0682 | **0.7071** | 0.7359 |

Mục tiêu p95 ≤ 1.5 s: upload **PASS** (p95 upload 0.7307 s); mọi request gộp upload và poll **PASS** (exit code theo số này). Lỗi: 0 . Từ lúc thả client tới khi xong: 12.38 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 36, 'ready': 4}.
Máy sinh tải dùng trung bình 0.23 CPU trong pha upload (được dùng 12). Ghim CPU: server không, client không.

CPU phía server trong pha upload (0.75 s), process dùng ≥ 0,05 CPU: api uvicorn cấp 1: luồng chính 0.32, cả process 1.21.

Tìm kiếm: 4 lượt mỗi client sau upload (wildcard `%`, `_`, `100%` và tiêu đề của client); kết quả sai: **0**. Khi có tìm kiếm, dòng upload phía server gộp cả GET `/api/v1/meetings` (histogram chỉ có nhãn route). Dòng "tất cả" chỉ gộp upload và poll.

Stdout của API: 485 dòng, trong đó 445 dòng access của app, 0 dòng access của uvicorn; dòng có query string: **0**.

Thư mục lưu (thư mục trống của lượt, STORAGE_DIR) có 0 thư mục lúc bắt đầu, 0 lúc kết thúc (đã xóa 45 thư mục audio và artifact của 40 meeting lượt này tạo).
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 1.3729 s, max 2.7576 s; 0/40 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 200 | 0.3418 | 0.25 – 0.5 | 0.5 – 0.75 | 1.0 | 1.0 |
| poll, tổng thời gian ở app | 200 | 0.0416 | 0.025 – 0.05 | 0.1 – 0.25 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 400 | 0.0105 | 0.0 – 0.001 | 0.025 – 0.05 | 1.0 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 1.0, ≤ 2,0 s = 1.0.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 200/200, poll 200/200 (1 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 40 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
