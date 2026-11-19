# 40 client có tìm kiếm `?q=` trên `main` sau #66 và #67 (VT-018, 2026-11-19)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `006fd8c`; `env.json` ghi `dde0a52` (thêm `--search` của harness; `backend/app` như `006fd8c`).
- **Cấu hình:** như [`../load-40-2026-11-17/README.md`](../load-40-2026-11-17/README.md), thêm `--search 4`: sau upload, mỗi client tìm 4 lượt (`%`, `_`, `100%`, tiêu đề của client). 1 process API, 1 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s, Postgres 16 cục bộ mới khởi tạo, một máy 12 CPU.
- **6 lượt liên tiếp** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s. Chạy từ 12:53 đến 12:57, ngay sau 9 lượt 247 client. Load average lúc bắt đầu lượt giảm từ 18,8 xuống 1,6. Thư mục lưu là `backend/appdata` thật: 22.950 thư mục audio cũ, không đổi qua 6 lượt.

## Kết quả

| Lượt | p95 upload (s) | p95 tìm kiếm (s) | CPU process API (luồng chính / cả process) |
|---|---|---|---|
| r1 | 0,44 | 0,20 | 0,30 / 1,10 |
| r2 | 0,38 | 0,21 | 0,31 / 1,16 |
| r3 | 0,48 | 0,21 | 0,29 / 0,99 |
| r4 | 0,47 | 0,20 | 0,29 / 0,99 |
| r5 | 0,49 | 0,20 | 0,26 / 0,98 |
| r6 | 0,49 | 0,20 | 0,34 / 1,17 |

p95 lấy từ `summary.json` (khóa `create`). **6/6 lượt đạt**, 0 lỗi trong 240 upload. 960 lượt tìm kiếm, 0 kết quả sai. Stdout của API mỗi lượt 485 dòng, 0 dòng access của uvicorn, 0 dòng có query string.

## Kết luận cho VT-018

Gộp 7 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6, 11-19: 6/6): **63/64 lượt đạt** p95 upload ≤ 1,5 s. Lượt không đạt vẫn là lượt 1,56 s ngày 11-12, chưa rõ nguyên nhân. Ở 40 client, thêm 160 lượt tìm kiếm mỗi lượt đo không làm upload vượt mốc: 0,38 đến 0,49 s, so với 0,41 đến 0,55 s ngày 11-17.

## Giới hạn

Một máy, pipeline fake, client là thread Python, 6 lượt trong 4 phút. Bảng chỉ có 40 cuộc họp. `GET /meetings` chạy một truy vấn `Job` cho mỗi cuộc họp trong trang (N+1), xem [`../../load-247/search-2026-11-19/README.md`](../../load-247/search-2026-11-19/README.md).
