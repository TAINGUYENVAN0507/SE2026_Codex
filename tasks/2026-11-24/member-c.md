# 2026-11-24 · Member C: giới hạn trường chữ trên PostgreSQL, 247 client 1 và 4 process với thư mục lưu trống, 40 client (Đợt 14, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:**
  - #71 đã merge (`6d5f94d`), kèm commit sửa CI `1eed9b8` của B.
  - C review #72 (A) và chạy lại E2E trang rỗng trên API thật: 3/3 passed. Sau đó merge `b35e06f`.
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app; chỉ test, công cụ đo, bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Test trên PostgreSQL cho 11 trường chữ API nhận: gửi giá trị dài hơn cột hoặc schema 1 ký tự, hoặc sai định dạng với cột ngắn, và đòi status 4xx. 4 ca hiện trả 500 được đánh `xfail(strict=True, raises=AssertionError)` kèm việc của B | `test(backend): every text field the API accepts answers 4xx one character past its limit on PostgreSQL, four 500s marked for B (BE-05, AD-018)` | `a6b0992` |
| 2 | [x] 247 client có tìm kiếm, 1 và 4 process xen kẽ (1 4 4 1 1 4), thư mục lưu trống | `test(backend): 247 clients with search on 1 and 4 API processes interleaved with an empty storage folder on main after #71 and #72 (AD-018)` | `6ebb45a` |
| 3 | [x] 40 client có tìm kiếm, thư mục lưu trống, 6 lượt | `test(backend): 40 clients with search and an empty storage folder on main after #71 and #72 (VT-018)` | `093f33c` |
| 4 | [x] Bản đồ bằng chứng (thêm dòng "Sửa đổi được" của AD-018), ROADMAP (kết quả Đợt 13, Đợt 14), thời gian phản hồi PR tới #72; giao việc 11-24 | `docs(evidence): evidence map with an editability row, PR response times and roadmap after #71 and #72; assign 2026-11-24 (RE-018, AD-018, VT-018)` | `23bbce2` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-24 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **#71:** CI đỏ vì `test_evidence_map_links` đọc chuỗi `backend/appdata` trong backtick thành đường dẫn file. Thư mục này có trên máy đo nhưng không có trên CI, nên chạy cục bộ vẫn đạt. B viết commit sửa `1eed9b8`. Từ hôm nay, C chạy test này với `backend/appdata` tạm cất đi để giống CI.
- **Review #72:** đọc diff, không có điểm chặn.
  - E2E trang rỗng: 3/3 passed. Lần đầu C chạy thiếu `E2E_MANUAL_WORKER=1` nên spec dừng ở guard; đó là lỗi của C.
  - Một điểm chuyển cho A (việc 4): dòng của trang cũ hiện như trang mới trong lúc tải.
- **Lỗi mới C tìm khi soạn việc:**
  - **Đổi tên cuộc họp thật không lưu lên API.** `RemoteMeetingContent` chỉ đổi state, và `frontend/src/api/client.ts` không có `PATCH /meetings/{id}`. Giao A, việc 1.
  - **Bốn trường trả 500 trên PostgreSQL:** `title` 201 ký tự, `meeting_date` sai định dạng, `Idempotency-Key` 101 ký tự ở `POST /meetings`, và `due_date` sai định dạng ở `POST /action-items`.
    - C thử `title` trên API thật: 200 ký tự trả 201, 201 ký tự trả 500 `StringDataRightTruncation`, 1000 ký tự thì kết nối bị reset.
    - Các test cũ dùng SQLite nên không thấy lỗi này. Giao B, việc 3.
  - **Ô sửa transcript không có `maxLength` 5000.** Giao A, việc 3.
- **247 client có tìm kiếm, thư mục lưu trống:**
  - 1 process: 3/3 trên mốc (2,68 đến 3,00 s). Thư mục trống không làm cấu hình mặc định đạt.
  - 4 process: 3/3 đạt (1,28 đến 1,37 s).
  - 0 kết quả tìm sai trong 5.928 lượt.
- **40 client:** 6/6 đạt (0,43 đến 0,55 s). Gộp 9 ngày: 75/76.
- **Phản hồi PR:** 13/41 PR có phản hồi của người khác, 9/13 trong 18 và 20 giờ. B chưa mở PR cho ngày 11-23. Ba việc của B chuyển sang 11-24.
- **Backend (PostgreSQL 16, `main` + 4 commit của C):**
  - **524 passed, 4 xfailed, 0 skipped.** 4 xfailed là 4 ca 500 ở trên.
  - `tests/unit` và `tests/contract` với `backend/appdata` tạm cất đi: 317 passed.
  - Ruff sạch (172 file).
  - `backend/appdata/audio` giữ 22.950 thư mục.
- **Còn mở:**
  - Đo lại 247 client sau khi B sửa N+1.
  - `API_WORKERS: 1` mặc định không đạt 247 client.
  - Lượt 1,56 s ngày 11-12 chưa rõ nguyên nhân.
  - Test xóa cuộc họp theo `STORAGE_DIR` để đợt sau.
  - Khoảng 22.934 thư mục WAV cũ của harness trong `backend/appdata` trên máy đo, C chưa xóa vì chưa được đồng ý.
