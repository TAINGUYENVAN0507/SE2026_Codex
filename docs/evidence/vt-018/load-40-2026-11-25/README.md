# 40 client có tìm kiếm, thư mục lưu trống, trên `main` sau #74 và #75 (VT-018, 2026-11-25)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `70b527a` (sau #74, #75, có bản sửa N+1); `env.json` ghi `9e4cebc` (thêm test của C; `backend/app` như `70b527a`).
- **Cấu hình:** như [`../load-40-2026-11-24/README.md`](../load-40-2026-11-24/README.md): `--search 4`, `--storage temp`, 1 process API, pipeline fake, Postgres 16 cục bộ, một máy 12 CPU.
- **6 lượt liên tiếp** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s, từ 14:40 đến 14:44, ngay sau 8 lượt 247 client. Load average lúc bắt đầu lượt giảm từ 10,9 xuống 1,9.

## Kết quả

| Lượt | p95 upload (s) | p95 tìm kiếm (s) | CPU process API (luồng chính / cả process) |
|---|---|---|---|
| r1 | 0,41 | 0,21 | 0,28 / 1,10 |
| r2 | 0,69 | 0,29 | 0,32 / 1,22 |
| r3 | 0,50 | 0,21 | 0,27 / 0,96 |
| r4 | 0,43 | 0,21 | 0,29 / 1,08 |
| r5 | 0,49 | 0,21 | 0,28 / 0,99 |
| r6 | 0,39 | 0,22 | 0,34 / 1,21 |

p95 lấy từ `summary.json` (khóa `create`). **6/6 lượt đạt**, 0 lỗi trong 240 upload. 960 lượt tìm kiếm, 0 kết quả sai. 0 dòng có query string. p95 tìm kiếm ở các lượt r3 đến r6 là 0,21 đến 0,22 s, ngang ngày 11-24 (0,22 đến 0,24 s).

## Kết luận cho VT-018

Gộp 10 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6, 11-19: 6/6, 11-23: 6/6, 11-24: 6/6, 11-25: 6/6): **81/82 lượt đạt** p95 upload ≤ 1,5 s. Lượt không đạt vẫn là lượt 1,56 s ngày 11-12, chưa rõ nguyên nhân.

## Giới hạn

Một máy, pipeline fake, client là thread Python, 6 lượt trong 4 phút. Bảng chỉ có 40 cuộc họp.
