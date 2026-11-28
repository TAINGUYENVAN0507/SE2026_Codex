# 247 client: 2 process và 4 process API xen kẽ, cùng ngân sách kết nối (AD-018, BE-05, 2026-11-28)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

Ngày 11-27, khi máy đo bận, 2 process không đạt lượt nào (0/8) và 4 process đạt 2/2, nhưng 4 process chỉ chạy sau, không xen kẽ. Hôm nay đo hai cấu hình xen kẽ để so trong cùng điều kiện.

| Tên | Process API | `API_MAX_INFLIGHT` | Kết nối tối đa |
|---|---|---|---|
| `p2` | 2 | 40 (mặc định) | 2 × 40 + 20 = 100 |
| `p4` | 4 | 20 | 4 × 20 + 20 = 100 |

- Tổng số request xử lý cùng lúc của hai cấu hình bằng nhau (80); khác nhau là chia cho bao nhiêu process.
- **Code:** `env.json` ghi `9edaf3b`, tức `main` `03f16fb` (sau #83, #84) cộng hai commit của C (pipeline và test); `backend/app` như `03f16fb`.
- **Cấu hình:** 4 process sinh tải, `--search 4`, thư mục lưu tạm, pipeline fake, Postgres 16 cục bộ (`max_connections` 100), DB tạo mới trước lượt đầu, một máy 12 CPU.
- **Thứ tự:** `p2 p4 p4 p2 p2 p4 p4 p2`, nghỉ 30 s ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), từ 16:17 đến 16:25.
- Trình duyệt và VS Code chạy cùng máy; ảnh chụp `ps` trước khi đo ở [`ps-before.txt`](ps-before.txt). Load average 1 phút lúc đó 2,5 (hôm qua 8,8).

## Kết quả

| Lượt | p95 upload (s) | p95 tìm kiếm (s) | Upload trung bình phía server (s) | Chờ admission trung bình (s) | Load lúc bắt đầu | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|---|---|---|
| p2-1 | 1,91 | 0,89 | 0,68 | 0,23 | 2,5 | 0,32 / 1,12; 0,37 / 1,13 |
| p4-2 | 1,18 | 0,75 | 0,46 | 0,16 | 7,8 | 0,32 / 0,97; 0,35 / 0,97; 0,37 / 0,99; 0,35 / 0,97 |
| p4-3 | 1,25 | 0,70 | 0,49 | 0,17 | 9,7 | 0,28 / 0,88; 0,28 / 0,88; 0,25 / 0,89; 0,27 / 0,88 |
| p2-4 | 1,57 | 1,01 | 0,66 | 0,23 | 6,2 | 0,32 / 1,12; 0,35 / 1,12 |
| p2-5 | 1,81 | 0,99 | 0,67 | 0,23 | 5,0 | 0,31 / 1,07; 0,30 / 1,08 |
| p4-6 | 1,43 | 0,72 | 0,50 | 0,17 | 6,0 | 0,30 / 0,85; 0,27 / 0,87; 0,31 / 0,87; 0,31 / 0,87 |
| p4-7 | 1,24 | 0,71 | 0,48 | 0,17 | 10,8 | 0,32 / 0,97; 0,32 / 0,92; 0,31 / 0,93; 0,30 / 0,93 |
| p2-8 | 1,68 | 0,98 | 0,65 | 0,22 | 6,4 | 0,32 / 1,13; 0,33 / 1,12 |

p95 lấy từ `summary.json` (khóa `create`). Cả 8 lượt: 0 lỗi trong 1.976 upload, 0 kết quả tìm sai, 0 dòng có query string.

| Cấu hình | p95 upload (s) | Trung bình | Đạt mốc 2,0 s |
|---|---|---|---|
| 2 process | 1,57 đến 1,91 | 1,74 | 4/4 |
| 4 process | 1,18 đến 1,43 | 1,28 | 4/4 |

- **4 process nhanh hơn ở cả 4 cặp**, trung bình 0,46 s, và hai khoảng không chồng nhau. Các lượt 4 process thường bắt đầu khi load cao hơn, nên chênh lệch không đến từ việc chúng được chạy lúc máy rảnh.
- **2 process đạt 4/4 hôm nay, 0/8 hôm qua.** `backend/app` đổi giữa hai ngày không ở đường upload (#84: giới hạn dẫn chứng, mã lỗi audio, worker). Khác biệt rõ nhất là máy bớt bận; kết quả 2 process vẫn phụ thuộc tải của máy.
- Mặc định `API_WORKERS: 1` không đo lại hôm nay.

## Giới hạn

Một máy dùng chung, pipeline fake, Postgres chung máy, mỗi cấu hình 4 lượt trong 8 phút. Load average đo lúc bắt đầu lượt, còn chịu ảnh hưởng của lượt trước.
