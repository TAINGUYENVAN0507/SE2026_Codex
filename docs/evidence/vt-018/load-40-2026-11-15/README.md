# 40 client: fsync khi commit và ghi file audio (VT-018, 2026-11-15)

Ngày 11-12, 6 lượt 40 client chia hai mức: 4 lượt quanh 0,5 s, 2 lượt quanh 1,4 đến 1,6 s (1 lượt p95 upload 1,56 s, không đạt). Ngày 11-13 đã loại ffprobe ([`../load-40-2026-11-13/README.md`](../load-40-2026-11-13/README.md)). Hôm nay kiểm hai nghi vấn còn lại. Người đo: C.

- **Code:** app là `main` `115c905` (sau #56, #57). `env.json` ghi `28c8883`, là commit test UTF-8 của C ngay sau đó, không đổi `backend/app`.
- **Cấu hình:** như 11-12 và 11-13: 1 process API, 1 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s. Postgres 16 cục bộ, cluster mới khởi tạo hôm nay, `max_connections=100`. Một máy 12 CPU, chạy chung VS Code.
- **Bốn biến thể, chạy xen kẽ 4 vòng** (`base-1`, `nosync-1`, `fresh-1`, `tmpfs-1`, `base-2`, ...), nghỉ 15 s giữa các lượt, 10:14 đến 10:23 ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)):
  - `base`: như các ngày trước. Thư mục lưu `backend/appdata` có sẵn 18.080 thư mục audio, dồn lại từ các lượt đo trước (harness tạo lại DB mỗi lượt nhưng không dọn file).
  - `nosync`: như `base`, thêm `?options=-csynchronous_commit%3Doff` vào URL DB. Commit không chờ WAL ghi xuống đĩa. Đã kiểm qua `get_session_factory()` của app: `SHOW synchronous_commit` trả `off` (URL thường trả `on`).
  - `fresh`: thư mục lưu rỗng, cùng ổ đĩa (`/dev/sda2`).
  - `tmpfs`: thư mục lưu rỗng trên RAM (`/dev/shm`).

`LocalStorage` cứng thư mục `backend/appdata`, không có biến môi trường, nên mỗi lượt `run.sh` đổi `appdata` thành symlink tới thư mục của biến thể (`base` và `nosync` trỏ về thư mục gốc), xong thì trả lại. Đã kiểm `fresh` và `tmpfs` có đúng 40 thư mục audio mới sau lượt đầu.

Lúc đo, `run.sh` truyền `--out` tuyệt đối nên `env.json` ghi đường dẫn có thư mục máy đo. Sau khi đo, C đổi trường đó sang đường dẫn tương đối trong 16 file `env.json` và sửa `run.sh` (dòng `REL=`) để lần sau ghi tương đối; các số khác giữ nguyên.

## Kết quả (p95 upload phía client, giây; trong ngoặc là trung bình upload phía server)

| Vòng | `base` | `nosync` | `fresh` | `tmpfs` |
|---|---|---|---|---|
| 1 | 0,43 (0,39) | 0,56 (0,50) | 0,37 (0,34) | 0,40 (0,37) |
| 2 | 0,53 (0,50) | 0,40 (0,37) | 0,41 (0,38) | 0,36 (0,33) |
| 3 | 0,46 (0,43) | 0,48 (0,45) | 0,34 (0,31) | 0,38 (0,35) |
| 4 | 0,73 (0,69) | 0,47 (0,44) | 0,45 (0,40) | 0,35 (0,32) |
| Trung bình | 0,54 | 0,48 | 0,39 | 0,37 |

p95 tính từ `raw.csv` (quantile theo hạng gần nhất). Chi tiết từng lượt: `<lượt>/summary.md`.

- **16/16 lượt đạt** p95 ≤ 1,5 s, 0 lỗi trong 640 upload. Không lượt nào rơi vào mức 1,4 đến 1,6 s của 11-12.
- **fsync khi commit không giải thích được mức chậm.** `nosync` nhanh hơn `base` ở 3/4 vòng, chậm hơn ở vòng 1; trung bình chỉ bớt 0,06 s.
- **Ghi audio lên đĩa hay lên RAM không khác nhau.** `fresh` và `tmpfs` mỗi bên nhanh hơn ở 2/4 vòng, trung bình chênh 0,02 s.
- **Thư mục lưu đầy hơn thì chậm hơn một chút, đều đặn.** Hai biến thể dùng thư mục 18.080 thư mục con (`base`, `nosync`) trung bình 0,51 s; hai biến thể dùng thư mục rỗng trung bình 0,38 s. `fresh` nhanh hơn `base` ở 4/4 vòng. Số phía server chênh tương tự, nên thời gian nằm trong app. Cơ chế chưa kiểm: mỗi upload tạo `audio/<meeting_id>/` trong thư mục cha đã rất lớn (file thư mục 1,1 MB).
- **Mức chậm 0,9 s của 11-12 vẫn không tái hiện được, nên chưa biết nguyên nhân.** Chênh lệch do thư mục đầy khoảng 0,13 s, nhỏ hơn nhiều. Ba nghi vấn đã kiểm (ffprobe ngày 11-13, fsync khi commit, ghi file audio) đều không cho ra mức đó.

## Kết luận cho VT-018

Gộp 4 ngày trên `main` (11-11: 6/6, 11-12: 5/6, 11-13: 12/12, 11-15: 16/16): **39/40 lượt đạt** p95 ≤ 1,5 s. Lượt không đạt là 1,56 s (11-12). Vẫn ghi là "đạt ở phần lớn lượt, có 1 lượt không đạt chưa rõ nguyên nhân", không ghi là đạt ổn định.

## Giới hạn

- Như các ngày trước: một máy, pipeline fake, client là thread Python. 16 lượt trong 9 phút cùng một trạng thái máy (load average lúc bắt đầu lượt 1,2 đến 3,3).
- **Thứ tự biến thể trong mỗi vòng là cố định** (`base` luôn chạy đầu vòng). Kết luận "thư mục đầy chậm hơn" vì vậy còn lẫn với thứ tự chạy; muốn tách thì phải đảo thứ tự giữa các vòng.
- `nosync` chỉ tắt chờ WAL khi commit; Postgres vẫn fsync ở checkpoint. Không thử `fsync=off` cho cả cluster.
- Harness không dọn file audio sau mỗi lượt, nên `backend/appdata` của máy đo lớn dần (1,8 GB hôm nay). Các lượt 40 client của những ngày trước chạy với thư mục đầy ở các mức khác nhau.
