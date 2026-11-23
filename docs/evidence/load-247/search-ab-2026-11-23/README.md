# 247 client, 2 process API, có và không có tìm kiếm xen kẽ trên `main` sau #69 và #70 (AD-018, BE-05, 2026-11-23)

Người đo: C. Mục tiêu AD-018: p95 upload ≤ 2,0 s ở 247 người dùng đồng thời.

Ngày 11-19, có tìm kiếm (`--search 4`), 2 process đạt 2/3: một lượt 2,52 s. Ngày 11-17, không có tìm kiếm, 2 process đạt 3/3 (1,38 đến 1,41 s). Hai ngày có load máy khác nhau, nên chưa biết phần chậm là do tìm kiếm hay do máy. Hôm nay chạy cả hai điều kiện xen kẽ trong cùng một khoảng thời gian.

- **Code:** `main` `5c29101`; `env.json` ghi `c34ed5c`. Đó là commit harness của C: API và worker ghi vào thư mục trống mỗi lượt qua `STORAGE_DIR` (`--storage temp`). `backend/app` giống `5c29101`.
- **Cấu hình:** 2 process API, 4 process sinh tải, 1 worker, pipeline fake, WAV im lặng 3 s, Postgres 16 cục bộ mới khởi tạo, một máy 12 CPU, không ghim CPU. Thư mục lưu trống mỗi lượt. Các ngày trước dùng `backend/appdata` thật với 22.950 thư mục.
- **Thứ tự:** ABBA ABBA, 8 lượt, nghỉ 30 s giữa hai lượt ([`run.sh`](run.sh), [`run-log.txt`](run-log.txt)), từ 12:37 đến 12:45. Load average lúc bắt đầu lượt từ 2,7 đến 6,4, thấp hơn 11-19 (lên tới 19,2).
- **Kết luận dùng p95 upload** (`create` trong `summary.json`).

## Kết quả

| Lượt | Tìm kiếm | p95 upload (s) | p50 upload (s) | p95 tìm kiếm (s) | CPU từng process API (luồng chính / cả process) |
|---|---|---|---|---|---|
| s0-1 | không | 2,01 | 1,52 | | 0,25 / 1,01; 0,27 / 0,95 |
| s4-2 | 4 mỗi client | 1,89 | 1,00 | 0,81 | 0,31 / 1,10; 0,32 / 1,10 |
| s4-3 | 4 mỗi client | 1,61 | 1,03 | 0,95 | 0,32 / 1,03; 0,29 / 1,08 |
| s0-4 | không | 1,71 | 1,33 | | 0,22 / 0,80; 0,23 / 0,84 |
| s0-5 | không | 1,38 | 1,00 | | 0,29 / 1,09; 0,29 / 0,98 |
| s4-6 | 4 mỗi client | 1,78 | 1,00 | 0,86 | 0,35 / 1,12; 0,33 / 1,13 |
| s4-7 | 4 mỗi client | 1,78 | 1,02 | 0,85 | 0,32 / 1,11; 0,35 / 1,11 |
| s0-8 | không | 1,55 | 0,98 | | 0,29 / 1,05; 0,26 / 1,07 |

Cả 8 lượt: 0 lỗi, 247 upload và 1.235 poll mỗi lượt. Bốn lượt có tìm kiếm gửi tổng cộng 3.952 lượt, **0 kết quả sai**. Stdout của API: 1.981 dòng ở lượt không tìm kiếm, 2.969 dòng ở lượt có tìm kiếm, **0 dòng có query string**. Thư mục lưu ở mọi lượt bắt đầu với 0 thư mục và kết thúc với 0 thư mục.

- **Không tìm kiếm:** p95 upload 1,38 đến 2,01 s, trung bình 1,66 s, đạt 3/4. Lượt không đạt là lượt đầu tiên (2,01 s, vượt mốc 0,01 s).
- **Có tìm kiếm:** p95 upload 1,61 đến 1,89 s, trung bình 1,77 s, đạt 4/4.
- **Tìm kiếm làm p95 upload tăng khoảng 0,1 s trung bình.** Mức này nhỏ hơn dao động trong cùng một điều kiện (0,63 s giữa các lượt không tìm kiếm), nên 4 cặp lượt không đủ để khẳng định có chênh. Lượt 2,52 s ngày 11-19 cao hơn mọi lượt có tìm kiếm hôm nay (1,61 đến 1,89 s), nên khó giải thích bằng tìm kiếm. Hôm đó load máy cao hơn, nhưng chưa chứng minh được đó là nguyên nhân.
- Ở lượt có tìm kiếm, CPU cả process tăng khoảng 0,1 (1,03 đến 1,13, so với 0,80 đến 1,09). Process vẫn ở quanh trần 1 CPU như các ngày trước.
- Lượt có tìm kiếm có p50 upload thấp hơn lượt không tìm kiếm cùng vòng (1,00 so với 1,52 và 1,33 ở hai lượt đầu). Mình chưa giải thích được điểm này và không dùng nó để kết luận.

## Giới hạn

- Một máy, pipeline fake, Postgres chung máy. Mỗi điều kiện 4 lượt.
- Hôm nay thư mục lưu trống, các ngày trước dùng thư mục đầy, nên không so trực tiếp với số tuyệt đối của 11-17 và 11-19. Ở 40 client, thư mục đầy chậm hơn 0,08 đến 0,13 s (11-15, 11-16).
- Chỉ đo 2 process. 1 process (mặc định của Compose) không đạt ở mọi ngày đo, kể cả khi không có tìm kiếm.
- `GET /meetings` vẫn chạy 1 truy vấn `Job` cho mỗi cuộc họp trong trang (N+1), giao B ở việc 2 ngày 11-23.
