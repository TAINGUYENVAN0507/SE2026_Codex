# 247 client: tách CPU của máy sinh tải, và A/B app (AD-018, 2026-11-15)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời. Ngày 11-11 không đạt ở cả hai cấu hình: 1 process API p95 upload 3,16 đến 3,79 s, 4 process 2,30 đến 2,60 s (15/15 lượt trên mốc, [`../after-2026-11-11/README.md`](../after-2026-11-11/README.md)). Khi đó có ghi một quan sát chưa kiểm: với 1 process, phần chênh giữa client và server "nằm trước middleware và ở máy sinh tải". Hôm nay kiểm phần "máy sinh tải".

- **Code:** app là `main` `115c905` (sau #56, #57). `env.json` ghi `91eb67a`: hai commit test và bằng chứng của C, không đổi `backend/app`. Harness lúc chạy là bản có `--server-cpus` và `--client-cpus`, chưa commit; commit cùng thư mục này mà không sửa thêm.
- **Môi trường:** 1 máy 12 CPU (6 nhân × 2 luồng), Postgres 16 cục bộ, cluster mới khởi tạo hôm nay, `max_connections=100`, `ssl=off`, kết nối TCP `127.0.0.1`. 1 worker, pipeline fake, WAV im lặng 3 s, 4 process sinh tải. Với 4 process API: `API_MAX_INFLIGHT=20`, như 11-10 và 11-11.
- **Hai cách chia CPU, xen kẽ 3 vòng** (`shared-1-1`, `pinned-1-1`, `shared-4-1`, `pinned-4-1`, ...; tên là `<cách chia>-<số process API>-<vòng>`), nghỉ 15 s giữa các lượt, 10:27 đến 10:36 ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)):
  - `shared`: mọi process dùng được cả 12 CPU, như các ngày trước.
  - `pinned`: API, worker và Postgres ghim vào nhân 0 đến 3 (CPU 0-3, 6-9); 4 process sinh tải ghim vào nhân 4 và 5 (CPU 4, 5, 10, 11). Chia theo nhân vật lý để hai bên không chung nhân qua hyper-threading. `env.json` ghi tập CPU đọc lại từ process API và worker (`affinity_read_back`).
- Mỗi lượt có `summary.json`, `summary.md`, `raw.csv`, `env.json`. Stdout của từng lượt (log JSON của server, khoảng 0,6 MB mỗi lượt) không giữ trong repo.

## Kết quả

"CPU sinh tải" là CPU time của 4 process sinh tải chia cho thời gian từ lúc thả tới upload cuối (`summary.json`, khóa `client_cpu`), tức số CPU máy sinh tải thật sự dùng trong pha upload.

| Process API | Vòng | `shared` p95 upload (s) | `shared` ≤ 2,0 s client / server | `shared` CPU sinh tải | `pinned` p95 upload (s) | `pinned` ≤ 2,0 s client / server | `pinned` CPU sinh tải |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 2,75 | 66,8 % / 68,8 % | 0,27 | 2,37 | 68,0 % / 100,0 % | 0,32 |
| 1 | 2 | 2,17 | 83,0 % / 100,0 % | 0,29 | 2,30 | 79,3 % / 100,0 % | 0,33 |
| 1 | 3 | 2,09 | 83,8 % / 100,0 % | 0,30 | 2,31 | 81,8 % / 100,0 % | 0,33 |
| 4 | 1 | 1,03 | 100,0 % / 100,0 % | 0,71 | 1,29 | 100,0 % / 100,0 % | 0,60 |
| 4 | 2 | 1,02 | 100,0 % / 100,0 % | 0,70 | 1,37 | 100,0 % / 100,0 % | 0,55 |
| 4 | 3 | 1,04 | 100,0 % / 100,0 % | 0,69 | 1,28 | 100,0 % / 100,0 % | 0,60 |

p95 tính từ `raw.csv` (quantile theo hạng gần nhất). 0 lỗi ở cả 12 lượt (2.964 upload). Server đếm 247/247 upload và 1.235/1.235 poll ở mọi lượt.

- **Máy sinh tải không phải nguyên nhân.** Trong pha upload, 4 process sinh tải chỉ dùng 0,27 đến 0,71 CPU trên 12. Ghim chúng sang nhân riêng không làm 1 process nhanh hơn: trung bình 2,33 s khi tách, 2,34 s khi chung. Câu "phần chênh ở máy sinh tải" của ngày 11-11 vì vậy không đứng.
- **1 process API: không đạt, 6/6 lượt trên 2,0 s** (2,09 đến 2,75 s). Phía server, 5/6 lượt có 100 % upload ≤ 2,0 s, còn phía client chỉ 67 đến 84 %. Phần chênh nằm ngoài khoảng middleware đo được, và không ở máy sinh tải. Còn lại là uvicorn một event loop nhận 247 kết nối và đọc request trước khi tới middleware; chưa đo riêng phần này.
- **4 process API: đạt, 6/6 lượt** (`shared` 1,02 đến 1,04 s, `pinned` 1,28 đến 1,37 s). Ghim làm 4 process chậm hơn vì server chỉ còn 8 CPU thay vì 12, nên ở cấu hình này server bị giới hạn bởi CPU.

## A/B app: có phải code từ 11-11 tới nay làm nhanh hơn? (`ab-app/`)

Ngày 11-11, 4 process `shared` là 2,30 đến 2,60 s; hôm nay là 1,02 đến 1,04 s. Từ `1f9d1ca` (11-11) tới `115c905`, `backend/app` có đổi metric, `jobs.py`, `meetings.py` (query budget của #51) và `summary.py` (#56), không có migration mới. Xen kẽ hai bản app, 4 process, `shared`, 3 cặp, 10:37 đến 10:42 ([`ab-app/run.sh`](ab-app/run.sh), [`ab-app/run-log.txt`](ab-app/run-log.txt)):

- `old-1f9d1ca`: `main` ngày 11-11, chạy từ một git worktree; `env.json` ghi `git_commit` `1f9d1ca`. Worktree dùng harness của hôm nay (chép vào, không commit) và symlink `appdata` về thư mục lưu của repo chính, nên hai bản chỉ khác nhau ở `backend/app`.
- `main-115c905`: `main` hôm nay.

| Cặp | `old-1f9d1ca` p95 upload (s) | `main-115c905` p95 upload (s) | chênh |
|---|---|---|---|
| 1 | 1,18 | 1,10 | −0,08 |
| 2 | 1,05 | 1,00 | −0,05 |
| 3 | 1,07 | 1,08 | +0,01 |

**Code không phải lý do.** App của ngày 11-11 hôm nay cũng chỉ 1,05 đến 1,18 s, đạt 3/3. Chênh lệch giữa hai ngày đến từ môi trường đo. Khác biệt đã biết so với 11-11: cluster Postgres mới khởi tạo; kết nối TCP `127.0.0.1` thay vì Unix socket mà các phiên đo trước dùng (theo lệnh trong phiên làm việc; `env.json` không ghi URL DB). Cả hai cluster đều `ssl=off`. Load average lúc đo hôm nay là 5 đến 22, không thấp hơn 11-11 (10 đến 16). Chưa kiểm riêng từng khác biệt, nên **chưa biết nguyên nhân**.

`env.json` của `old-1f9d1ca` ban đầu ghi `--out` là đường dẫn tương đối tính từ worktree, có thư mục máy đo; C đổi trường đó sang đường dẫn trong repo, các số khác giữ nguyên.

## Kết luận cho AD-018

| Cấu hình | 11-10 | 11-11 | 11-15 | Ghi |
|---|---|---|---|---|
| 1 process API (mặc định, Compose không đặt `API_WORKERS`) | 14/14 lượt trên mốc | 3/3 trên mốc | 6/6 trên mốc (2,09 đến 2,75 s) | **Không đạt** |
| 4 process API, `API_MAX_INFLIGHT=20` | 10/12 đạt | 0/15 đạt (2,30 đến 2,60 s) | 9/9 đạt trên `main` (1,00 đến 1,37 s; gồm 3 lượt `pinned` và 3 lượt A/B) | **Đạt ở hôm nay và 11-10, không đạt ở 11-11.** Nguyên nhân chênh giữa các ngày chưa rõ, và không phải do code. Không ghi là đạt ổn định |

## Giới hạn

- Một máy, pipeline fake, client là thread Python, như các ngày trước. Mỗi cấu hình 3 lượt trong khoảng 15 phút cùng một trạng thái máy.
- `pinned` cho server 8 CPU và máy sinh tải 4 CPU, không phải hai máy riêng.
- Postgres chạy ngoài harness, nên `run.sh` ghim nó bằng `taskset` (postmaster và các process con; backend mới kế thừa). `env.json` chỉ đọc lại tập CPU của API và worker, không đọc của Postgres.
- Harness không dọn file audio sau mỗi lượt, nên `backend/appdata` lớn dần trong lúc đo (trên 18.000 thư mục). Ở 40 client, thư mục lưu đầy chậm hơn thư mục rỗng khoảng 0,13 s ([`../../vt-018/load-40-2026-11-15/README.md`](../../vt-018/load-40-2026-11-15/README.md)).
