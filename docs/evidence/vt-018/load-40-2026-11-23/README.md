# 40 client có tìm kiếm, thư mục lưu trống và thư mục thật xen kẽ, trên `main` sau #69 và #70 (VT-018, 2026-11-23)

Người đo: C. Mục tiêu VT-018: p95 upload ≤ 1,5 s ở 40 người dùng đồng thời.

- **Code:** `main` `5c29101`; `env.json` ghi `c34ed5c` (thêm `--storage` của harness; `backend/app` như `5c29101`).
- **Cấu hình:** như [`../load-40-2026-11-19/README.md`](../load-40-2026-11-19/README.md), cũng `--search 4`. Khác ở chỗ thư mục lưu đổi theo từng lượt:
  - `temp`: thư mục trống mỗi lượt, API và worker nhận qua `STORAGE_DIR`.
  - `real`: `backend/appdata` thật, có 22.950 thư mục audio cũ.
- **6 lượt, thứ tự ABBAAB** ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), nghỉ 15 s. Chạy từ 12:45 đến 12:49, ngay sau 8 lượt 247 client. Load average lúc bắt đầu lượt 1,5 đến 4,6.

## Kết quả

| Lượt | Thư mục lưu | p95 upload (s) | p95 tìm kiếm (s) | CPU process API (luồng chính / cả process) |
|---|---|---|---|---|
| temp-1 | trống | 0,49 | 0,30 | 0,31 / 1,18 |
| real-2 | 22.950 thư mục | 0,41 | 0,21 | 0,33 / 1,12 |
| real-3 | 22.950 thư mục | 0,40 | 0,22 | 0,35 / 1,18 |
| temp-4 | trống | 0,39 | 0,21 | 0,35 / 1,20 |
| temp-5 | trống | 0,41 | 0,22 | 0,31 / 1,18 |
| real-6 | 22.950 thư mục | 0,66 | 0,23 | 0,22 / 0,80 |

p95 lấy từ `summary.json` (khóa `create`). **6/6 lượt đạt**, 0 lỗi trong 240 upload. 960 lượt tìm kiếm, 0 kết quả sai. 0 dòng có query string. Ở lượt `real`, thư mục thật vẫn 22.950 thư mục trước và sau lượt. Ở lượt `temp`, thư mục lưu bắt đầu với 0 thư mục và kết thúc với 0 thư mục.

- **Thư mục trống:** 0,39 đến 0,49 s, trung bình 0,43 s.
- **Thư mục thật:** 0,40 đến 0,66 s, trung bình 0,49 s.
- Chênh trung bình 0,06 s, chủ yếu do lượt `real-6` (0,66 s). Không lặp lại được mức chênh 0,08 đến 0,13 s của 11-15 và 11-16 một cách rõ ràng: hai lượt `real` khác nhanh ngang lượt `temp`.

## Kết luận cho VT-018

Gộp 8 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12, 11-17: 6/6, 11-19: 6/6, 11-23: 6/6): **69/70 lượt đạt** p95 upload ≤ 1,5 s. Lượt không đạt vẫn là lượt 1,56 s ngày 11-12, chưa rõ nguyên nhân. Từ hôm nay harness mặc định dùng thư mục lưu trống, nên lượt đo không còn ghi vào `backend/appdata` thật.

## Giới hạn

Một máy, pipeline fake, client là thread Python, 6 lượt trong 4 phút. Bảng chỉ có 40 cuộc họp.
