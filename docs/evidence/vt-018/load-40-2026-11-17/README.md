# 40 client trên `main` sau #61 và #64 (VT-018, 2026-11-17)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `1dc6b5c`; `env.json` ghi `bacc9c3` (thêm harness đếm log; `backend/app` như `1dc6b5c`).
- **Cấu hình:** như [`../load-40-2026-11-16/README.md`](../load-40-2026-11-16/README.md): 1 process API, 1 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s, Postgres 16 cục bộ mới khởi tạo, một máy 12 CPU.
- **6 lượt liên tiếp** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s. 12:51 đến 12:55. Thư mục lưu là `backend/appdata` thật (22.950 thư mục audio cũ, không đổi qua 6 lượt vì harness tự dọn phần của nó). Load average lúc bắt đầu lượt 3,2 đến 4,7.

## Kết quả

| Lượt | p95 upload (s) | CPU process API (luồng chính / cả process) |
|---|---|---|
| r1 | 0,42 | 0,26 / 1,04 |
| r2 | 0,41 | 0,26 / 1,03 |
| r3 | 0,55 | 0,28 / 1,16 |
| r4 | 0,54 | 0,29 / 1,07 |
| r5 | 0,51 | 0,27 / 1,13 |
| r6 | 0,51 | 0,21 / 0,83 |

p95 từ `summary.json` (khóa `create`). 6/6 lượt đạt, 0 lỗi trong 240 upload. Stdout của API mỗi lượt 325 dòng, 0 dòng có query string.

## Kết luận cho VT-018

Gộp 6 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6): **57/58 lượt đạt** p95 upload ≤ 1,5 s. Lượt không đạt vẫn là 1,56 s ngày 11-12, chưa rõ nguyên nhân. #61 (thêm một truy vấn gộp ở meeting detail) và #64 không làm 40 client chậm đi. Vẫn ghi "đạt ở phần lớn lượt, có 1 lượt không đạt chưa rõ nguyên nhân".

## Giới hạn

Một máy, pipeline fake, client là thread Python, 6 lượt trong 4 phút. Harness không gọi `GET /meetings/{id}`, nên truy vấn gộp của #61 chưa được tải đo trực tiếp; chỉ có test ngân sách truy vấn (`test_poll_query_budget.py`).
