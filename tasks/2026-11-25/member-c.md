# 2026-11-25 · Member C: giới hạn của các endpoint ghi còn lại, 247 client trước và sau bản sửa N+1, 40 client (Đợt 15, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** C review #74 (A) và #75 (B), CI xanh 12/12 và 16/16. C gộp hai PR với `main` rồi chạy trên PostgreSQL 16 trước khi merge: 536 passed, 1 skipped. Sau đó merge `46feb59` rồi `70b527a`.
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app; chỉ test, công cụ đo, bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Thêm 11 ca vào test giới hạn trên PostgreSQL: sửa công việc, đổi tên người nói, đổi người nói của segment, `PUT /summary`, đăng nhập. 10 ca trả 4xx đúng. Ca dẫn chứng tóm tắt trỏ tới segment không tồn tại thì trả 200, được đánh `xfail(strict=True)` và giao B | `test(backend): the remaining write endpoints answer 4xx past their limits on PostgreSQL; summary evidence ids outside the meeting marked for B (BE-05, AD-018, FE-18)` | `9e4cebc` |
| 2 | [x] 247 client, 2 process, `b35e06f` (trước #75) và `main` (sau #75) xen kẽ ABBA ABBA, 8 lượt. Đo riêng thêm `GET /meetings` của hai bản | `test(backend): 247 clients on 2 API processes before and after the meeting list N+1 fix interleaved, with GET /meetings timed alone (AD-018, BE-05)` | `ebc1705` |
| 3 | [x] 40 client có tìm kiếm, 6 lượt | `test(backend): 40 clients with search on main after #74 and #75 (VT-018)` | `531c2e7` |
| 4 | [x] Bản đồ bằng chứng (dòng "Sửa đổi được" đổi thành "Có, trừ một điểm"), ROADMAP (kết quả Đợt 14, Đợt 15), thời gian phản hồi PR tới #75; giao việc 11-25 | `docs(evidence): evidence map, PR response times and roadmap after #74 and #75; assign 2026-11-25 (RE-018, AD-018, VT-018)` | `255243e` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-25 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **Review #74:** không có điểm chặn. Ghi chú "thiếu `maxLength`" của B không đúng: dòng 272 có `maxLength={200}`.
- **Review #75:**
  - Finding P2 của A đúng. C tái hiện với hai job cùng `created_at`: danh sách trả `...002`, chi tiết trả `...001`. Lỗi mới do #75 đưa vào. C vẫn merge vì cần bản sửa N+1 để đo, và giao B việc 1.
  - #75 có 6 commit, trong đó refactor `bde32b7` không có trong việc được giao.
- **Lỗi mới C tìm khi soạn việc:**
  - `audio.size_bytes` luôn bằng 0. Giao B.
  - `PUT /summary` nhận dẫn chứng là segment không thuộc cuộc họp. Giao B.
  - Trên cuộc họp thật, tóm tắt không dừng ở 50 mục, và ô công việc, ô tổng quan không có giới hạn độ dài. Giao A.
- **247 client trước và sau bản sửa N+1:**

  | Bản | p95 upload | Đạt mốc 2,0 s |
  |---|---|---|
  | Trước #75 | 1,72 đến 1,95 s | 4/4 |
  | Sau #75 | 1,76 đến 2,45 s | 1/4 |

  - Bản sửa không làm 247 client nhanh hơn.
  - Đo riêng `GET /meetings` (1 client, 300 request): bản sau nhanh hơn ở 3/4 phép so. Mỗi request chỉ 10 đến 40 ms, nên phần chậm của lượt "sau" không đến từ danh sách. Nguyên nhân chưa rõ, cần đo thêm.
- **40 client:** 6/6 đạt (0,39 đến 0,69 s). Gộp 10 ngày: 81/82.
- **Phản hồi PR:** 15/44 PR có phản hồi của người khác, 11/15 trong 18 và 20 giờ. Cả hai PR của Đợt 14 được review chéo trong hạn.
- **Backend (PostgreSQL 16, `main` + 4 commit của C):**
  - **546 passed, 1 skipped, 1 xfailed.** Test bị skip là `test_db_fixture.py:103`, vì Postgres của C chỉ nghe IPv4; trên CI test này chạy. 1 xfailed là ca dẫn chứng giao B.
  - `tests/unit` và `tests/contract` với `backend/appdata` tạm cất đi: 319 passed, 1 skipped.
  - Ruff sạch (174 file).
- **Còn mở:**
  - Nguyên nhân 247 client chậm hơn sau #75.
  - `API_WORKERS: 1` mặc định không đạt 247 client.
  - Lượt 1,56 s ngày 11-12 chưa rõ nguyên nhân.
  - Khoảng 22.934 thư mục WAV cũ của harness trong `backend/appdata` trên máy đo, C chưa xóa vì chưa được đồng ý.
