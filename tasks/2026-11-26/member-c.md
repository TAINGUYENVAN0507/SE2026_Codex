# 2026-11-26 · Member C: chữ của từng ý trong tóm tắt, 247 client ba bản xen kẽ, 40 client (Đợt 16, sau hạn nộp)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:**
  - C review #77 (A) và #78 (B); CI xanh 12/12 và 16/16.
  - C gộp hai PR với `main` rồi chạy lại trước khi merge:
    - Backend trên PostgreSQL 16: 551 passed, 1 skipped, 0 xfailed. Mở thêm `::1` thì test bị skip cũng đạt.
    - Frontend: lint, 341 passed, 0 skipped, build.
    - E2E `summary-edit.spec.ts` trên API thật: 1 passed.
  - Merge `3dd5ae0` (#78) rồi `db8072b` (#77). `main` sau merge giống hệt bản đã chạy (diff 0 dòng).
- **Phạm vi:** sau hạn nộp 11-14. Không đổi code app; chỉ test, công cụ đo, bằng chứng.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Thêm 5 ca `xfail` strict cho `PUT /summary`: ý chính và quyết định 1001 ký tự, ý rỗng, quyết định chỉ có khoảng trắng, tổng quan chỉ có khoảng trắng. Cả 5 đang trả 200. Thêm ca biên 1000 ký tự (lưu được) và ca bảo vệ (tóm tắt đã lưu dài 5000 ký tự vẫn đọc được 200). Giao B | `test(backend): summary points longer than 1000 characters or blank are still saved on PostgreSQL, marked for B; stored long points must keep reading (BE-05, FE-12, AD-018)` | `113a5bb` |
| 2 | [x] 247 client, 2 process, ba bản `b35e06f` (trước #75), `70b527a` (sau #75), `main` (sau #78) xen kẽ ABCCBA ABCCBA, 12 lượt | `test(backend): 247 clients on 2 API processes across three builds interleaved: before #75, after #75, and main after #78 (AD-018, BE-05)` | `e0bc731` |
| 3 | [x] 40 client có tìm kiếm, 6 lượt; thêm 4 lượt để thử giả thuyết "lượt đầu trên DB mới" | `test(backend): 40 clients with search on main after #77 and #78, one run over 1.5 s and a fresh-database check that does not explain it (VT-018)` | `f583a0b` |
| 4 | [x] Bản đồ bằng chứng, ROADMAP (kết quả Đợt 15, Đợt 16), thời gian phản hồi PR tới #78; giao việc 11-26 | `docs(evidence): evidence map, PR response times and roadmap after #77 and #78; assign 2026-11-26 (RE-018, AD-018, VT-018)` | `c52999b` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-26 member C results (G0)` | commit này |

## Kết quả và điều còn mở

- **Review #77:** không có điểm chặn.
  - P3: nhánh `details === null` nhận mọi `VALIDATION_ERROR` của `POST /meetings`.
  - P3: trường `identity` trong `useIdempotencyKey` không được đọc.
  - Review của B ghi sai tên hai hằng.
- **Review #78:** không có điểm chặn.
  - P3: `available` vẫn true khi file mất. Thành việc 2 của B.
  - P3: nhánh `hasattr` thừa. Gộp vào việc 2 của B.
- **Lỗi mới C tìm:**
  - `PUT /summary` không giới hạn chữ của mỗi ý, và API không giới hạn body JSON.
  - Handler validation gán câu "Nội dung đoạn thoại…" cho mọi lỗi có `"text"` trong `loc`, kể cả ý của tóm tắt.
  - Ba chỗ tìm file audio theo ba cách.
  - Player báo "hết hạn" cả khi chỉ là mất file.
- **247 client, ba bản:**

  | Bản | p95 upload | Đạt mốc 2,0 s |
  |---|---|---|
  | Trước #75 | 1,63 đến 2,85 s | 3/4 |
  | Sau #75 | 1,49 đến 2,30 s | 3/4 |
  | `main` sau #78 | 1,58 đến 1,74 s | 4/4 |

  - Lượt chậm hơn của "sau #75" ngày 11-25 không lặp lại.
  - Hai lượt không đạt là hai lượt cuối, khi load máy cao nhất.
  - Gộp hai ngày: trước #75 7/8, sau #75 4/8. Nhưng `main` có cùng đường upload với bản sau #75 lại đạt 4/4, nên dao động giữa các lượt lớn hơn mọi chênh lệch. C không kết luận #75 làm chậm.
- **40 client:**
  - 5/6 đạt. r1 không đạt (1,55 s), cùng dạng lượt 1,56 s ngày 11-12: hai mức, thời gian nằm trong app.
  - 4 lượt thêm (2 trên DB mới, 2 trên DB đã dùng) đều đạt, nên giả thuyết "lượt đầu trên DB mới" bị bác. Nguyên nhân chưa rõ.
  - Gộp 11 ngày: 86/88.
- **Phản hồi PR:** 17/47 PR có phản hồi của người khác, 13/17 trong 18 và 20 giờ. A không review #78.
- **Backend (PostgreSQL 16 nghe IPv4 và IPv6, `main` + 4 commit của C):**
  - **554 passed, 0 skipped, 5 xfailed, 28 warning.** 5 xfailed là 5 ca giao B.
  - 28 warning gồm: 20 `HTTP_422_UNPROCESSABLE_ENTITY`, 1 `HTTP_413_REQUEST_ENTITY_TOO_LARGE`, 6 `cookies=` theo request, 1 `httpx` với TestClient. Phần tên mã HTTP giao B (việc 4).
  - `test_evidence_map_links` với `backend/appdata` tạm cất đi: 2 passed.
  - Ruff sạch (175 file).
- **Còn mở:**
  - Lượt 40 client trên 1,5 s (11-12, 11-26) chưa rõ nguyên nhân.
  - `API_WORKERS: 1` mặc định không đạt 247 client.
  - 247 client ở 2 process phụ thuộc load máy.
  - Khoảng 22.934 thư mục WAV cũ của harness trong `backend/appdata` trên máy đo. C chưa xóa vì chưa được đồng ý.
