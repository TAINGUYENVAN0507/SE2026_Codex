# Kết quả tải VT-018 (247 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 247 | 1.9234 | 3.0249 | 3.3261 |
| poll trạng thái job | 1235 | 0.0277 | 0.1142 | 0.3891 |
| tìm kiếm `?q=` | 988 | 1.2103 | 1.8347 | 2.0658 |
| **tất cả** | 1482 | 0.0373 | **2.4571** | 3.3261 |

Mục tiêu p95 ≤ 2.0 s: upload **FAIL** (p95 upload 3.0249 s); mọi request gộp upload và poll **FAIL** (exit code theo số này). Lỗi: 0 . Từ lúc thả client tới khi xong: 17.87 s. Process sinh tải: 4.
Trạng thái meeting khi kết thúc: {'queued': 100}.
Máy sinh tải dùng trung bình 0.34 CPU trong pha upload (được dùng 12). Ghim CPU: server không, client không.

CPU phía server trong pha upload (3.42 s), process dùng ≥ 0,05 CPU: api uvicorn cấp 1: luồng chính 0.38, cả process 1.16.

Tìm kiếm: 4 lượt mỗi client sau upload (wildcard `%`, `_`, `100%` và tiêu đề của client); kết quả sai: **0**. Khi có tìm kiếm, dòng upload phía server gộp cả GET `/api/v1/meetings` (histogram chỉ có nhãn route). Dòng "tất cả" chỉ gộp upload và poll.

Stdout của API: 2969 dòng, trong đó 2722 dòng access của app, 0 dòng access của uvicorn; dòng có query string: **0**.

Thư mục lưu `appdata/audio` có 22950 thư mục lúc bắt đầu, 22950 lúc kết thúc (đã xóa 255 thư mục audio và artifact của 247 meeting lượt này tạo).
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 6.849 s, max 12.0795 s; 156/247 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 1235 | 1.2133 | 1.0 – 1.5 | 1.5 – 2.0 | 0.7717 | 0.9935 |
| poll, tổng thời gian ở app | 1235 | 0.0324 | 0.01 – 0.025 | 0.05 – 0.1 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 2470 | 0.5087 | 0.0 – 0.001 | 1.5 – 2.0 | 0.9381 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 0.4089, ≤ 2,0 s = 0.5951.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 1235/1235, poll 1235/1235 (1 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (4 process, 62 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
