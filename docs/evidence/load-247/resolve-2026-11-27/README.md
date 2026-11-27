# 247 client trước và sau #81 (tìm file audio dùng chung) xen kẽ, khi máy đo đang bận (AD-018, BE-05, 2026-11-27)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

#81 (B) thay cách tìm file audio bằng `resolve_audio_file`: `resolve()`, `is_relative_to(base_dir)` và `is_file()` cho mỗi mục của `GET /meetings` và chi tiết. Hôm nay đo để xem thay đổi này có làm 247 client chậm hơn không.

| Tên | Bản app | Ghi trong `env.json` |
|---|---|---|
| `pre81` | `main` hôm qua `db8072b` (sau #77, #78) | `db8072b` |
| `main` | `main` `4259a4f` (sau #80, #81) | `9c45de5`: `main` cộng commit test của C, `backend/app` như `4259a4f` |

- **Cấu hình:** 2 process API, 4 process sinh tải, `--search 4`, thư mục lưu tạm, pipeline fake, Postgres 16 cục bộ (`max_connections` 100), một máy 12 CPU.
- `pre81` chạy trong worktree tạm, nên `out` là `run-<lượt>` rồi được chép về đây. Harness và `uv.lock` giống hệt ở hai bản.
- **Thứ tự:** ABBA ABBA, 8 lượt, nghỉ 30 s ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), từ 09:50 đến 10:01.

## Máy đo đang bận

Khác các ngày trước, hôm nay máy đo đang được dùng trong lúc đo: trình duyệt và VS Code chạy cùng.
- Sau 8 lượt, khi C không chạy gì, load average 1 phút vẫn là 8,8.
- Ảnh chụp `ps` lúc đó: VS Code khoảng 26 % + 14 % CPU, trình duyệt khoảng 20 % + 10 % + 9 % CPU, Xorg 7 %, gnome-shell 7 %.
- CPU governor là `powersave`.

Hai bản vẫn chạy xen kẽ trong cùng điều kiện, nên phép so giữa hai bản còn dùng được. Còn số tuyệt đối hôm nay không so được với các ngày máy rảnh.

## Kết quả, 2 process

| Lượt | Bản | p95 upload (s) | p95 tìm kiếm (s) | Upload trung bình phía server (s) | Load lúc bắt đầu | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|---|---|---|
| 1 | pre81 | 2,81 | 1,63 | 1,13 | 1,6 | 0,33 / 1,11; 0,33 / 1,10 |
| 2 | main | 3,01 | 1,83 | 1,33 | 6,2 | 0,30 / 1,04; 0,32 / 1,06 |
| 3 | main | 2,28 | 1,17 | 0,85 | 11,4 | 0,31 / 1,13; 0,31 / 1,14 |
| 4 | pre81 | 2,96 | 1,30 | 0,97 | 7,7 | 0,25 / 0,98; 0,27 / 0,97 |
| 5 | pre81 | 7,73 | 3,59 | 1,95 | 6,2 | 0,33 / 1,05; 0,30 / 1,05 |
| 6 | main | 4,16 | 2,21 | 1,63 | 8,1 | 0,30 / 1,11; 0,30 / 1,10 |
| 7 | main | 4,74 | 2,35 | 1,69 | 10,0 | 0,30 / 1,11; 0,31 / 1,10 |
| 8 | pre81 | 4,32 | 2,18 | 1,67 | 12,4 | 0,31 / 1,11; 0,30 / 1,10 |

Cả 8 lượt: 0 lỗi, 0 kết quả tìm sai, 0 dòng có query string.

| Bản | p95 upload (s) | Trung bình | Đạt mốc 2,0 s |
|---|---|---|---|
| pre81 | 2,81; 2,96; 7,73; 4,32 | 4,45 | 0/4 |
| main | 3,01; 2,28; 4,16; 4,74 | 3,55 | 0/4 |

- **Không thấy #81 làm chậm.** `main` trung bình nhanh hơn `pre81` 0,90 s, nhưng dao động trong mỗi bản (2,28 đến 7,73 s) lớn hơn nhiều so với chênh lệch đó.
- **Cả 8 lượt 2 process đều không đạt**, kể cả `db8072b`, bản hôm qua đạt 4/4 (1,58 đến 1,74 s) khi máy rảnh. Vì vậy phần chậm hôm nay đến từ máy, không từ code.

## Kết quả, 4 process (thêm sau 8 lượt)

Chạy thêm 2 lượt `main` với 4 process API ([`run-4proc.sh`](run-4proc.sh)), dùng ngân sách kết nối như 11-24: `API_MAX_INFLIGHT=20`, tức 4 × 20 + 20 = 100 kết nối.

Hai lần thử đầu lỗi ngay ở bước `alembic`, vì C quên đặt `API_MAX_INFLIGHT=20`. Khi đó `Settings` chặn đúng: 4 × 40 + 20 = 180 vượt 100. Các dòng của hai lần thử đó đã được bỏ khỏi `run-log.txt`.

| Lượt | p95 upload (s) | p95 tìm kiếm (s) | Upload trung bình phía server (s) | Load lúc bắt đầu |
|---|---|---|---|---|
| main4p-1 | 1,55 | 1,06 | 0,69 | 2,4 |
| main4p-2 | 1,61 | 1,02 | 0,67 | 6,2 |

Cả 2 lượt đạt, 0 lỗi, 0 kết quả tìm sai. Khi máy bận, 4 process vẫn đạt mốc 2,0 s, còn 2 process thì không.

## Giới hạn

- Một máy dùng chung, pipeline fake, Postgres chung máy, mỗi bản 4 lượt.
- Không đo được tải của các ứng dụng khác theo từng lượt; chỉ có load average và một ảnh chụp `ps`.
