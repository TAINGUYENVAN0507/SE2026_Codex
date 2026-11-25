# 247 client, 2 process API, trước và sau bản sửa N+1 (#75) xen kẽ (AD-018, BE-05, 2026-11-25)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

#75 (B) gộp phần lấy job mới nhất của mọi cuộc họp trong trang `GET /meetings` vào một truy vấn. Trước đó mỗi mục chạy thêm một `select(Job)`, tức N+1. Hôm nay đo bản trước và bản sau xen kẽ, cùng harness và cùng DB, để xem bản sửa có làm 247 client nhanh hơn không.

- **Trước:** app tại `b35e06f` (trước #74, #75), chạy trong một worktree tạm. `env.json` ghi `b35e06f`, và `out: run-before-N` vì lượt chạy trong worktree rồi được chép về đây. Harness ở `b35e06f` giống hệt harness trên `main` (C kiểm bằng `diff`).
- **Sau:** `main` `70b527a` (sau #74, #75); `env.json` ghi `9e4cebc`, tức `main` cộng commit test của C, `backend/app` như `70b527a`.
- **Cấu hình:** 2 process API, 4 process sinh tải, `--search 4`, `--storage temp`, pipeline fake, Postgres 16 cục bộ, một máy 12 CPU.
- **Thứ tự:** ABBA ABBA, 8 lượt, nghỉ 30 s ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), từ 14:32 đến 14:40. Load average lúc bắt đầu lượt 1,7 đến 10,4.

## Kết quả

| Lượt | App | p95 upload (s) | p95 tìm kiếm (s) | p50 tìm kiếm (s) | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|---|---|
| before-1 | trước | 1,95 | 0,99 | 0,63 | 0,34 / 1,14; 0,37 / 1,12 |
| after-2 | sau | 1,76 | 0,83 | 0,59 | 0,37 / 1,14; 0,33 / 1,14 |
| after-3 | sau | 2,45 | 1,32 | 0,80 | 0,33 / 1,10; 0,30 / 1,08 |
| before-4 | trước | 1,87 | 0,88 | 0,60 | 0,36 / 1,12; 0,33 / 1,12 |
| before-5 | trước | 1,72 | 0,86 | 0,58 | 0,32 / 1,12; 0,36 / 1,13 |
| after-6 | sau | 2,15 | 1,09 | 0,70 | 0,37 / 1,11; 0,35 / 1,11 |
| after-7 | sau | 2,13 | 0,99 | 0,81 | 0,32 / 1,06; 0,33 / 1,05 |
| before-8 | trước | 1,81 | 0,91 | 0,60 | 0,35 / 1,11; 0,34 / 1,12 |

Cả 8 lượt: 0 lỗi, 0 kết quả tìm sai, 0 dòng có query string.

- **Trước:** p95 upload 1,72 đến 1,95 s, trung bình 1,84 s, đạt 4/4.
- **Sau:** p95 upload 1,76 đến 2,45 s, trung bình 2,12 s, đạt 1/4.
- **Bản sửa N+1 không làm 247 client nhanh hơn.** Bốn lượt sau còn chậm hơn trung bình 0,28 s, và p50 tìm kiếm cũng cao hơn (0,59 đến 0,81 s so với 0,58 đến 0,63 s). Dao động trong nhóm "sau" lớn (0,69 s), nên 4 cặp lượt chưa đủ để nói #75 làm chậm. Trước đó, ở 2 process, mức dao động giữa các ngày đã là 1,38 đến 2,52 s.

## Đo riêng `GET /meetings`

Để biết phần chậm có nằm ở danh sách không, C đo riêng endpoint này trên cùng DB 247 cuộc họp: 1 client, 300 request tuần tự, 2 vòng ([`listbench.py`](listbench.py), số đo ở [`listbench.txt`](listbench.txt)).

| Vòng | Truy vấn | Trước: median / p95 (ms) | Sau: median / p95 (ms) |
|---|---|---|---|
| 1 | danh sách 10 mục | 12,1 / 52,8 | 8,5 / 25,2 |
| 1 | `q=Tải 1`, 10 mục | 11,8 / 14,4 | 9,0 / 28,2 |
| 1 | `q=%`, 0 mục | 5,8 / 7,8 | 6,9 / 18,6 |
| 2 | danh sách 10 mục | 16,8 / 65,5 | 17,6 / 27,6 |
| 2 | `q=Tải 1`, 10 mục | 40,6 / 59,3 | 20,7 / 27,5 |
| 2 | `q=%`, 0 mục | 13,4 / 17,2 | 13,6 / 20,4 |

- Với trang có 10 mục, bản sau thường nhanh hơn: median thấp hơn ở 3/4 phép so, p95 thấp hơn ở 3/4. Với `q=%` (0 mục, không có N+1) hai bản ngang nhau.
- Mỗi request danh sách chỉ tốn khoảng 10 đến 40 ms, rất nhỏ so với p95 upload khoảng 2 s. Phần chậm hơn của lượt "sau" ở bảng trên vì vậy không đến từ `GET /meetings`. Nguyên nhân chưa rõ.

## Giới hạn

- Một máy, pipeline fake, Postgres chung máy, mỗi bản 4 lượt.
- Bản "trước" chạy từ worktree trong thư mục tạm, có virtualenv riêng (cùng `uv.lock`).
- Phép đo riêng chỉ có 1 client, nên không thấy được tranh chấp khi có tải.
