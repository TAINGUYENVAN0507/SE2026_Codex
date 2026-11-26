# 40 client có tìm kiếm, thư mục lưu trống, trên `main` sau #77 và #78 (VT-018, 2026-11-26)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `db8072b` (sau #77, #78). `env.json` ghi `e0bc731`, tức `main` cộng hai commit test và bằng chứng của C; `backend/app` như `db8072b`.
- **Cấu hình:** như [`../load-40-2026-11-25/README.md`](../load-40-2026-11-25/README.md): `--search 4`, `--storage temp`, 1 process API, pipeline fake, Postgres 16 cục bộ, một máy 12 CPU.
- **6 lượt liên tiếp** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s, từ 09:25 đến 09:29.
  - Chạy 2 phút sau 12 lượt 247 client.
  - Load average 1 phút lúc bắt đầu lượt giảm từ 5,7 xuống 3,1; load 5 phút lúc bắt đầu r1 là 9,9.
  - DB `load40` được tạo mới hôm nay, nên r1 là lượt đầu tiên trên DB đó.

## Kết quả

| Lượt | p95 upload (s) | p95 tìm kiếm (s) | Upload trung bình phía server (s) | CPU process API (luồng chính / cả process) |
|---|---|---|---|---|
| r1 | **1,55** | 0,86 | 0,61 | 0,38 / 1,12 |
| r2 | 0,53 | 0,29 | 0,24 | 0,30 / 1,05 |
| r3 | 0,48 | 0,28 | 0,23 | 0,32 / 1,21 |
| r4 | 0,49 | 0,29 | 0,24 | 0,32 / 1,09 |
| r5 | 0,47 | 0,28 | 0,23 | 0,31 / 1,13 |
| r6 | 0,48 | 0,30 | 0,23 | 0,31 / 1,17 |

p95 lấy từ `summary.json` (khóa `create`). **5/6 lượt đạt.** 0 lỗi trong 240 upload, 960 lượt tìm kiếm, 0 kết quả sai, 0 dòng có query string.

**Lượt r1 không đạt** (1,55 s), ngang lượt 1,56 s ngày 11-12, và có cùng dạng:
- Hai mức tách rõ: r1 có p50 1,12 s, còn các lượt khác khoảng 0,5 s.
- Thời gian nằm trong app: upload trung bình phía server 0,61 s ở r1, so với 0,24 s ở r2.
- Chờ admission thấp ở mọi lượt (trung bình 0,02 s ở r1).

## Thử giả thuyết "lượt đầu trên DB mới"

r1 là lượt đầu tiên trên DB vừa tạo, nên C chạy thêm hai vòng ([`run-fresh.sh`](run-fresh.sh)). Mỗi vòng xóa và tạo lại DB, chạy `fresh`, rồi chạy `warm` trên cùng DB.

| Lượt | p95 upload (s) | Upload trung bình phía server (s) |
|---|---|---|
| fresh1 | 0,48 | 0,24 |
| warm1 | 0,52 | 0,24 |
| fresh2 | 0,49 | 0,26 |
| warm2 | 0,87 | 0,30 |

Cả 4 lượt đạt, và lượt trên DB mới không chậm hơn. **Giả thuyết bị bác.** Ngày 11-12, lượt chậm cũng là lượt 2, không phải lượt đầu. Điều khác còn lại của r1 là chạy ngay sau 12 lượt 247 client, nhưng ngày 11-25 cũng chạy ngay sau 247 client mà 6/6 đạt. **Nguyên nhân chưa rõ.**

## Kết luận cho VT-018

- Gộp 11 ngày trên `main` theo cách đếm như các ngày trước, chưa tính 4 lượt thêm hôm nay (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6, 11-19: 6/6, 11-23: 6/6, 11-24: 6/6, 11-25: 6/6, 11-26: 5/6): **86/88 lượt đạt** p95 upload ≤ 1,5 s.
- Nếu tính cả 4 lượt thêm hôm nay: 90/92.
- Hai lượt không đạt (1,56 s ngày 11-12, 1,55 s ngày 11-26) có cùng dạng hai mức, thời gian nằm trong app. Mốc 1,5 s đạt ở phần lớn lượt, nhưng chưa ổn định trên máy dùng chung.

## Giới hạn

Một máy, pipeline fake, client là thread Python, 10 lượt trong 7 phút. Không đo được thời gian chờ CPU của từng request.
