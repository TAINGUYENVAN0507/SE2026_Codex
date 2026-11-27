# 2026-11-27 · Member C: danh sách dẫn chứng trên PostgreSQL, 247 client trước và sau #81 khi máy bận, 40 client (Đợt 17, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:**
  - C review #80 (A) và #81 (B); CI xanh 12/12 và 19/19.
  - C gộp hai PR với `main` rồi chạy lại trước khi merge:
    - Backend trên PostgreSQL 16 nghe IPv4 và IPv6: 568 passed, 0 skipped, 0 xfailed, 7 warning.
    - Frontend: lint, 352 passed, build.
    - E2E `evidence-seek.spec.ts` và `summary-edit.spec.ts` trên API thật: mỗi spec 1 passed.
  - Merge `6c84724` (#81) rồi `4259a4f` (#80). `main` sau merge giống hệt bản đã chạy (diff 0 dòng).
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app; chỉ test, công cụ đo, bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Test danh sách dẫn chứng của `PUT /summary` trên PostgreSQL: 70.000 id trả 500 (`xfail` strict, giao B), id dài 10.000 ký tự trả 422, id lặp được lưu nguyên. Kiểm thêm: 30.000 id trả 4xx, nên ngưỡng nằm ở giới hạn 65.535 tham số | `test(backend): a summary point with 70000 evidence ids answers 500 on PostgreSQL past its 65535 parameter limit, marked for B; long and repeated ids pinned (BE-05, FE-18, AD-018)` | `9c45de5` |
| 2 | [x] 247 client, 2 process, `db8072b` (trước #81) và `main` (sau #81) xen kẽ ABBA ABBA, 8 lượt, khi máy đo đang bận; thêm 2 lượt 4 process | `test(backend): 247 clients before and after the shared audio lookup (#81) interleaved on a busy machine, with 4 API processes as a check (AD-018, BE-05)` | `f8ec95c` |
| 3 | [x] 40 client có tìm kiếm, 6 lượt | `test(backend): 40 clients with search on main after #80 and #81 on a busy machine (VT-018)` | `eee84c9` |
| 4 | [x] Bản đồ bằng chứng, ROADMAP (kết quả Đợt 16, Đợt 17), thời gian phản hồi PR tới #81; giao việc 11-27 | `docs(evidence): evidence map, PR response times and roadmap after #80 and #81; assign 2026-11-27 (RE-018, AD-018, VT-018)` | `56faa4e` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-27 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **Review #80:** không có điểm chặn.
  - Việc giao hôm qua của C ghi sai mã `AUDIO_NOT_FOUND`; A bắt cả `NOT_FOUND`, đúng với API thật.
  - Phản hồi review #77 của A nằm trong file repo, "chưa đăng trên GitHub".
- **Review #81:** không có điểm chặn. Ba ghi chú P3; hai ghi chú thành việc 2 và việc 3 của B hôm nay.
- **Không có review chéo trong Đợt 16:** B không review #80, A không review #81.
- **Lỗi mới C tìm:**
  - `PUT /summary` với 70.000 id dẫn chứng trả 500.
  - Stack E2E ghi audio vào `backend/appdata` thật vì không đặt `STORAGE_DIR`.
  - Đăng nhập khi API trả 503 báo lỗi chung và xóa mật khẩu.
- **247 client:**

  | Bản | Số process | p95 upload | Đạt mốc 2,0 s |
  |---|---|---|---|
  | Trước #81 | 2 | 2,81 đến 7,73 s | 0/4 |
  | Sau #81 | 2 | 2,28 đến 4,74 s | 0/4 |
  | Sau #81 | 4 | 1,55 và 1,61 s | 2/2 |

  - Máy đo đang bận (trình duyệt, VS Code): load average 8,8 khi C không chạy gì.
  - Không thấy #81 làm chậm.
  - 2 process không đạt khi máy bận, kể cả bản hôm qua đạt 4/4.
- **Lỗi của C:**
  - Hai lần thử 4 process đầu tiên lỗi vì C quên `API_MAX_INFLIGHT=20` (ngân sách kết nối 4 × 40 + 20 = 180 vượt 100). Đã ghi trong README.
  - Lượt E2E đầu tiên hôm qua đỏ vì C đặt nhầm `E2E_MANUAL_WORKER=1`.
- **40 client:** 6/6 đạt (0,46 đến 0,82 s). Gộp 12 ngày: 92/94.
- **Phản hồi PR:** 19/50 PR có phản hồi của người khác, 14/19 trong 18 và 20 giờ. #80 có phản hồi đầu tiên sau 20,9 giờ, quá hạn.
- **Backend (PostgreSQL 16 nghe IPv4 và IPv6, `main` + 4 commit của C):**
  - **570 passed, 0 skipped, 1 xfailed, 7 warning.** 1 xfailed là ca 70.000 id giao B.
  - `test_evidence_map_links` với `backend/appdata` tạm cất đi: 2 passed.
  - Ruff sạch (175 file).
- **Còn mở:**
  - Hai lượt 40 client trên 1,5 s (11-12, 11-26) chưa rõ nguyên nhân.
  - 247 client ở 2 process phụ thuộc tải của máy; `API_WORKERS: 1` mặc định không đạt.
  - Khoảng 22.934 thư mục WAV cũ của harness trong `backend/appdata` trên máy đo. C chưa xóa vì chưa được đồng ý.
