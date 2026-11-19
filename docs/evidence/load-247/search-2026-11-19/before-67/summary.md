# Kết quả tải VT-018 (5 client đồng thời)

| Loại | n | p50 (s) | p95 (s) | max (s) |
|---|---|---|---|---|
| tạo cuộc họp (upload) | 5 | 0.1208 | 0.1293 | 0.1293 |
| poll trạng thái job | 5 | 0.0372 | 0.0492 | 0.0492 |
| tìm kiếm `?q=` | 20 | 0.0291 | 0.0396 | 0.0396 |
| **tất cả** | 10 | 0.0728 | **0.1293** | 0.1293 |

Mục tiêu p95 ≤ 1.5 s: upload **PASS** (p95 upload 0.1293 s); mọi request gộp upload và poll **FAIL** (exit code theo số này). Lỗi: 10 {'search_wrong:%': 5, 'search_wrong:_': 5}. Từ lúc thả client tới khi xong: 0.48 s. Process sinh tải: 1.
Trạng thái meeting khi kết thúc: {'queued': 5}.
Máy sinh tải dùng trung bình 0.12 CPU trong pha upload (được dùng 12). Ghim CPU: server không, client không.

CPU phía server trong pha upload (0.13 s), process dùng ≥ 0,05 CPU: api python cấp 1: luồng chính 0.23, cả process 0.77.

Tìm kiếm: 4 lượt mỗi client sau upload (wildcard `%`, `_`, `100%` và tiêu đề của client); kết quả sai: **10**. Khi có tìm kiếm, dòng upload phía server gộp cả GET `/api/v1/meetings` (histogram chỉ có nhãn route). Dòng "tất cả" chỉ gộp upload và poll.

Stdout của API: 45 dòng, trong đó 40 dòng access của app, 0 dòng access của uvicorn; dòng có query string: **0**.

Thư mục lưu `appdata/audio` có 0 thư mục lúc bắt đầu, 0 lúc kết thúc (đã xóa 6 thư mục audio và artifact của 5 meeting lượt này tạo).
Kết nối nằm rảnh từ lúc đăng nhập tới lúc upload: p50 0.1451 s, max 0.1705 s; 0/5 quá 5 s (timeout keep-alive mặc định của uvicorn). Lỗi upload chi tiết: `summary.json`, khóa `create_error_detail`.

## Phía server (`/metrics`, hiệu giữa lúc thả barrier và lúc mọi client xong)

| Loại | n | trung bình (s) | p50 trong khoảng (s) | p95 trong khoảng (s) | tỷ lệ ≤ 1,5 s | tỷ lệ ≤ 2,0 s |
|---|---|---|---|---|---|---|
| upload, tổng thời gian ở app | 25 | 0.0431 | 0.025 – 0.05 | 0.1 – 0.25 | 1.0 | 1.0 |
| poll, tổng thời gian ở app | 5 | 0.0322 | 0.025 – 0.05 | 0.025 – 0.05 | 1.0 | 1.0 |
| chờ admission (mọi request, không tách route) | 30 | 0.0 | 0.0 – 0.001 | 0.0 – 0.001 | 1.0 | 1.0 |

Phía client cùng lượt, upload: tỷ lệ ≤ 1,5 s = 1.0, ≤ 2,0 s = 1.0.
Từ bucket chỉ biết quantile nằm trong khoảng; tỷ lệ dưới mốc 1,5 và 2,0 là chính xác vì đó là biên bucket.
Thời gian ở app gồm chờ admission. Client trừ server là phần ngoài app: máy sinh tải, loopback, uvicorn trước middleware.
Số request server đếm / client gửi: create 25/25, poll 5/5 (1 process API).

## Giới hạn của phép đo

- Worker chạy mỗi lúc 1 job, hàng đợi dài dần trong lúc đo; đây là độ trễ của API, không phải thông lượng pipeline.
- Pipeline là fake, audio WAV im lặng 3 giây; chưa phản ánh tải của ASR/diarize thật.
- Client, API, worker và Postgres chung một máy (12 CPU), nên tranh chấp CPU làm số đo xấu hơn môi trường tách riêng.
- Client là thread Python (1 process, 5 thread mỗi process); số phía client gồm cả thời gian chờ GIL của máy sinh tải.
- Một lần chạy, chưa lặp để lấy khoảng tin cậy. Chi tiết máy ở `env.json`, từng request ở `raw.csv`.
