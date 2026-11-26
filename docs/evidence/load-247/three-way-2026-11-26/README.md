# 247 client, 2 process API, ba bản app xen kẽ: trước #75, sau #75, `main` sau #78 (AD-018, BE-05, 2026-11-26)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

Ngày 11-25, bốn lượt sau bản sửa N+1 (#75) chậm hơn bốn lượt trước trung bình 0,28 s ([`../n-plus-one-2026-11-25/README.md`](../n-plus-one-2026-11-25/README.md)). Hôm nay đo lại để xem điều đó có lặp lại không. Có thêm bản `main` sau #78, vì #78 thêm một lần `stat` file audio cho mỗi mục của `GET /meetings`.

| Tên | Bản app | Ghi trong `env.json` |
|---|---|---|
| `pre75` | `b35e06f` (trước #74, #75) | `b35e06f` |
| `post75` | `70b527a` (sau #75, trước #77, #78) | `70b527a` |
| `main` | `main` `db8072b` (sau #77, #78) | `113a5bb`: `main` cộng commit test của C, `backend/app` như `db8072b` |

- **Cấu hình:** 2 process API, 4 process sinh tải, `--search 4`, thư mục lưu tạm (mặc định), pipeline fake, Postgres 16 cục bộ, một máy 12 CPU.
- `pre75` và `post75` chạy trong worktree tạm, mỗi worktree có virtualenv riêng. `out` của hai bản này là `run-<lượt>` vì lượt chạy trong worktree rồi được chép về đây.
- Harness (`backend/scripts`) và `uv.lock` giống hệt ở ba bản (C kiểm bằng `git diff`).
- **Thứ tự:** ABCCBA ABCCBA, 12 lượt, nghỉ 30 s ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), từ 09:10 đến 09:23. Load average lúc bắt đầu lượt 1,4 đến 14,3.

## Kết quả

| Lượt | Bản | p95 upload (s) | p95 tìm kiếm (s) | p50 tìm kiếm (s) | Load lúc bắt đầu | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|---|---|---|
| 1 | pre75 | 1,63 | 1,16 | 0,61 | 1,4 | 0,32 / 1,08; 0,30 / 1,08 |
| 2 | post75 | 1,84 | 0,86 | 0,61 | 9,8 | 0,36 / 1,12; 0,33 / 1,13 |
| 3 | main | 1,74 | 1,09 | 0,66 | 12,2 | 0,30 / 1,10; 0,34 / 1,09 |
| 4 | main | 1,58 | 0,97 | 0,59 | 8,2 | 0,36 / 1,11; 0,32 / 1,10 |
| 5 | post75 | 1,73 | 0,81 | 0,59 | 5,2 | 0,33 / 1,14; 0,33 / 1,13 |
| 6 | pre75 | 1,70 | 0,93 | 0,58 | 4,7 | 0,35 / 1,13; 0,32 / 1,12 |
| 7 | pre75 | 1,72 | 0,81 | 0,58 | 10,7 | 0,32 / 1,12; 0,32 / 1,13 |
| 8 | post75 | 1,49 | 1,00 | 0,58 | 6,7 | 0,32 / 1,06; 0,30 / 1,07 |
| 9 | main | 1,74 | 0,93 | 0,63 | 5,7 | 0,33 / 1,11; 0,34 / 1,10 |
| 10 | main | 1,64 | 1,08 | 0,70 | 6,7 | 0,33 / 1,10; 0,33 / 1,11 |
| 11 | post75 | **2,30** | 1,06 | 0,71 | 14,3 | 0,31 / 1,06; 0,28 / 1,03 |
| 12 | pre75 | **2,85** | 1,43 | 0,69 | 12,3 | 0,29 / 1,00; 0,32 / 0,98 |

Cả 12 lượt: 0 lỗi, 0 kết quả tìm sai, 0 dòng có query string.

| Bản | p95 upload (s) | Trung bình | Đạt mốc 2,0 s |
|---|---|---|---|
| pre75 | 1,63; 1,70; 1,72; 2,85 | 1,98 | 3/4 |
| post75 | 1,84; 1,73; 1,49; 2,30 | 1,84 | 3/4 |
| main | 1,74; 1,58; 1,74; 1,64 | 1,67 | 4/4 |

## Kết luận

- **Lượt chậm hơn của "sau #75" ngày 11-25 không lặp lại.** Hôm nay `post75` trung bình nhanh hơn `pre75`.
- Hai lượt không đạt là hai lượt cuối (11 và 12), thuộc hai bản khác nhau, và là hai lượt có load máy lúc bắt đầu cao nhất (14,3 và 12,3). CPU của process API ở hai lượt đó không cao hơn các lượt khác, nên phần chậm có vẻ đến từ máy, không từ app.
- **Gộp hai ngày:**
  - `pre75` (`b35e06f`): 7/8 đạt.
  - `post75` (`70b527a`): 4/8 đạt.
  - `main` sau #78: 4/4 đạt (chỉ đo hôm nay).
  - `main` và `post75` có cùng đường xử lý upload; #78 chỉ thêm `stat` ở các endpoint đọc. Vậy mà `main` đạt 4/4 còn `post75` đạt 4/8. Mức dao động giữa các lượt vì thế lớn hơn mọi chênh lệch giữa các bản đo được ở đây.
  - **C không kết luận #75 làm chậm, cũng không kết luận #78 làm nhanh.**
- **`stat` của #78 không làm chậm 247 client:** `main` có p95 upload 1,58 đến 1,74 s, hẹp nhất trong ba bản.
- **AD-018 ở 2 process vẫn là "đạt phần lớn lượt":** hôm nay 10/12. Kết quả phụ thuộc load máy, nên chưa thể nói là đạt ổn định.

## Giới hạn

- Một máy, pipeline fake, Postgres chung máy, mỗi bản 4 lượt.
- Không có phép đo thời gian chờ CPU của từng request. "Do load máy" là suy ra từ load average, chưa đo trực tiếp.
