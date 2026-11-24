# 40 client có tìm kiếm, thư mục lưu trống, trên `main` sau #71 và #72 (VT-018, 2026-11-24)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `b35e06f`; `env.json` ghi `a6b0992` (thêm test giới hạn trường của C; `backend/app` như `b35e06f`).
- **Cấu hình:** như [`../load-40-2026-11-23/README.md`](../load-40-2026-11-23/README.md), có `--search 4`, và cả 6 lượt đều dùng thư mục lưu trống (`--storage temp`, mặc định).
- **6 lượt liên tiếp** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s. Chạy từ 18:03 đến 18:07, ngay sau 6 lượt 247 client. Load average lúc bắt đầu lượt giảm từ 12,7 xuống 2,0.

## Kết quả

| Lượt | p95 upload (s) | p95 tìm kiếm (s) | CPU process API (luồng chính / cả process) |
|---|---|---|---|
| r1 | 0,55 | 0,22 | 0,23 / 0,93 |
| r2 | 0,43 | 0,22 | 0,32 / 1,12 |
| r3 | 0,49 | 0,24 | 0,28 / 1,05 |
| r4 | 0,46 | 0,23 | 0,30 / 1,04 |
| r5 | 0,53 | 0,23 | 0,27 / 0,95 |
| r6 | 0,50 | 0,23 | 0,27 / 0,99 |

p95 lấy từ `summary.json` (khóa `create`). **6/6 lượt đạt**, 0 lỗi trong 240 upload. 960 lượt tìm kiếm, 0 kết quả sai. 0 dòng có query string.

## Kết luận cho VT-018

Gộp 9 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6, 11-19: 6/6, 11-23: 6/6, 11-24: 6/6): **75/76 lượt đạt** p95 upload ≤ 1,5 s. Lượt không đạt vẫn là lượt 1,56 s ngày 11-12, chưa rõ nguyên nhân.

## Giới hạn

Một máy, pipeline fake, client là thread Python, 6 lượt trong 4 phút. Bảng chỉ có 40 cuộc họp.
