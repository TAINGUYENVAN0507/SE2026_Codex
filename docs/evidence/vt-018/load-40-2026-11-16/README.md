# 40 client: thư mục lưu đầy và rỗng, đổi thứ tự giữa các vòng (VT-018, 2026-11-16)

Người đo: C.

Ngày 11-15, hai biến thể dùng thư mục lưu đầy (18.080 thư mục audio) trung bình chậm hơn hai biến thể dùng thư mục rỗng khoảng 0,13 s. Nhưng thứ tự trong vòng cố định (`base` luôn chạy đầu vòng), nên chưa tách được khỏi thứ tự chạy ([`../load-40-2026-11-15/README.md`](../load-40-2026-11-15/README.md)). Hôm nay đổi thứ tự giữa các vòng.

- **Code:** app là `main` `3ed9c0d` (`backend/app` như `115c905`). `env.json` ghi `6f58a11`. Harness có ba thay đổi của C hôm nay:
  - Xóa file của các meeting lượt đo tạo, nên `full` giữ nguyên số thư mục qua các lượt (`95878ba`).
  - Ghi CPU phía server (`6f58a11`).
  - Ghi riêng kết luận theo p95 upload. Lúc chạy chưa commit; commit cùng thư mục này mà không sửa thêm.
- **Cấu hình:** như 11-12 đến 11-15.
  - 1 process API, 1 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s.
  - Postgres 16 cục bộ: cluster mới khởi tạo hôm nay, `max_connections=100`, TCP `127.0.0.1`.
  - Một máy 12 CPU, chạy chung VS Code.
- **Hai biến thể, 6 vòng, xen kẽ.** Vòng lẻ chạy `full` rồi `empty`, vòng chẵn chạy `empty` rồi `full`. Nghỉ 15 s giữa các lượt ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)).
  - `full`: thư mục lưu `backend/appdata` của máy đo, 22.947 thư mục audio dồn từ các lượt trước 11-16.
  - `empty`: thư mục rỗng mới cho mỗi lượt, cùng ổ đĩa (`/dev/sda2`).
  - `LocalStorage` cứng thư mục `backend/appdata`, nên `run.sh` đổi `appdata` thành symlink tới thư mục của biến thể rồi trả lại, như 11-15.
- 12:30 đến 12:38. Load average lúc bắt đầu lượt 1,8 đến 6,4.
- Đã kiểm qua `summary.json` (`storage_cleanup`):
  - Mỗi lượt `full` bắt đầu và kết thúc với 22.947 thư mục audio.
  - Mỗi lượt `empty` bắt đầu với 0 thư mục.
  - Mỗi lượt xóa đúng file của 40 meeting nó tạo (43 đến 45 thư mục: 40 audio, cộng artifact của các job worker kịp chạy).
- `summary.md` từ hôm nay có hai kết luận: theo p95 upload (dùng ở đây), và theo mọi request như trước.

## Kết quả (p95 upload phía client, giây; trong ngoặc là trung bình upload phía server)

| Vòng | Chạy trước | `full` | `empty` | `full` − `empty` |
|---|---|---|---|---|
| 1 | `full` | 0,38 (0,36) | 0,48 (0,43) | −0,10 |
| 2 | `empty` | 0,45 (0,43) | 0,39 (0,37) | +0,06 |
| 3 | `full` | 0,63 (0,57) | 0,45 (0,42) | +0,17 |
| 4 | `empty` | 0,55 (0,51) | 0,39 (0,36) | +0,15 |
| 5 | `full` | 0,64 (0,60) | 0,43 (0,39) | +0,21 |
| 6 | `empty` | 0,44 (0,41) | 0,45 (0,42) | 0,00 |
| Trung bình | | 0,52 (0,48) | 0,43 (0,40) | +0,08 |

p95 tính từ `raw.csv` (quantile theo hạng gần nhất). Chi tiết từng lượt: `<lượt>/summary.md`.

- **12/12 lượt đạt** p95 ≤ 1,5 s, 0 lỗi trong 480 upload. Không lượt nào rơi vào mức 1,4 đến 1,6 s của 11-12.
- **Thứ tự chạy không phải lý do.** Lượt chạy trước trong vòng trung bình 0,48 s, lượt chạy sau 0,47 s.
- **Thư mục đầy chậm hơn, nhưng không đều.**
  - Trung bình `full` chậm hơn `empty` 0,08 s (11-15: 0,13 s, khi thứ tự cố định). Số phía server chênh tương tự (0,48 và 0,40 s), nên thời gian nằm trong app.
  - Chỉ 4/6 vòng chậm hơn; vòng 1 nhanh hơn, vòng 6 bằng. Chênh từng vòng từ −0,10 đến +0,21 s.
  - Với 6 cặp, chưa đủ để nói chắc là có. Nếu có thì nhỏ so với mốc 1,5 s, và nhỏ hơn nhiều mức chậm 0,9 s của 11-12.
- **CPU phía server** (cột mới của harness): process API dùng 1,04 đến 1,16 CPU trong pha upload, luồng chính 0,23 đến 0,32 CPU. Ở 40 client, process cũng chạm trần khoảng 1 CPU như ở 247 client ([`../../load-247/event-loop-2026-11-16/README.md`](../../load-247/event-loop-2026-11-16/README.md)), nhưng pha upload chỉ 0,40 đến 0,65 s.

## Kết luận cho VT-018

Gộp 5 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16, 11-16: 12/12): **51/52 lượt đạt** p95 upload ≤ 1,5 s. Lượt không đạt là 1,56 s (11-12), chưa rõ nguyên nhân. Bốn nghi vấn đã loại hoặc chỉ giải thích được phần nhỏ: ffprobe (11-13), fsync khi commit, ghi đĩa hay RAM (11-15), và thư mục lưu đầy (11-15, 11-16; trung bình 0,08 đến 0,13 s). Vẫn ghi "đạt ở phần lớn lượt, có 1 lượt không đạt chưa rõ nguyên nhân", không ghi là đạt ổn định.

## Giới hạn

- Như các ngày trước: một máy, pipeline fake, client là thread Python. 12 lượt trong 8 phút, cùng một trạng thái máy.
- `full` là một thư mục đầy cụ thể (22.947 thư mục con, file thư mục 1,5 MB). Chưa thử nhiều mức đầy.
- Từ 11-16 harness tự dọn, nên các lượt sau này chạy với thư mục không lớn thêm. Các lượt trước 11-16 chạy với thư mục đầy ở các mức khác nhau, không ghi số.
