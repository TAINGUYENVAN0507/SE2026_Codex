# 2026-11-13 · Member C: xóa dữ liệu trên Postgres thật, chẩn đoán lượt 40 client chậm, đóng băng bằng chứng (Đợt 8)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #53 (A) đã vào `main` (C review diff, CI xanh 12/12, merge `a75853d`). B push 4 commit lên `haquang` ngày 11-12 nhưng chưa mở PR; C mở thay (#54) và merge khi CI xanh.
- **Mục tiêu:** ngày cuối trước hạn nộp 11-14. Không đổi code app. Chỉ thêm test, công cụ đo và sửa bằng chứng sai.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Test xóa cuộc họp và xóa tài khoản trên Postgres đã migrate thật. Khi review #54 thấy `test_delete_meeting.py`, `test_delete_user.py` và `test_privacy_canary.py` cứng `sqlite:///:memory:` và tự viết lại trigger `edit_events`, trong khi `docs/evidence/ad-018/README.md` ghi log "trên PostgreSQL 16". Test mới điền mọi bảng (gồm `jobs`, `ai_outputs`, `edit_events`), chạy hai mutant trên service xóa | `test(backend): erasure on migrated Postgres with every table populated (AD-018, BE-18)` | `8cf3f5b` |
| 2 | [x] Sửa bằng chứng xóa dữ liệu: log UTF-8 đọc được trên GitHub, bảng nơi lưu → test khớp với assert thật, "chưa có test" ở chỗ chưa có | `docs(evidence): deletion matrix matches the real asserts (AD-018)` | `cc6151d` |
| 3 | [x] Chẩn đoán hai mức thời gian ở 40 client: 6 cặp lượt xen kẽ ffprobe thật / ffprobe giả, cùng `main`, cùng máy | `test(backend): interleaved 40-client runs to isolate the slow mode (VT-018)` | `7d2bc95` |
| 4 | [x] Sinh lại thời gian phản hồi PR tới #54; bản đồ bằng chứng và ROADMAP theo `main` cuối (bỏ dòng "chưa" đã lỗi thời về metric stage) | `docs(evidence): final evidence map, PR response times and roadmap (RE-018, AD-018, VT-018)` | `5f62239` |
| 5 | [x] Tick, hash | `docs(tasks): record 2026-11-13 member C results (G0)` | commit này |

## Kết quả và điều còn mở

Ngoài 5 commit: `0a901af` (giao việc). Trước đó C review diff và merge #53 (A, CI xanh 12/12, `a75853d`); mở #54 thay B, review, merge khi CI xanh 15/15 (`f255e01`).

- **Xóa dữ liệu trên Postgres (AD-018):**
  - Ba test xóa cũ cứng `sqlite:///:memory:`, nên log "trên PostgreSQL 16" của #54 thật ra là SQLite.
  - Test mới chạy trên Postgres đã migrate, mọi bảng con có dữ liệu, đếm dòng trước và sau: 2 passed. Mutant bỏ xóa `idempotency_keys` bị bắt; mutant bỏ `delete(EditEvent)` sống vì FK cascade của Postgres làm cùng việc (tương đương, không phải lỗi).
  - Không tìm ra lỗi xóa trên Postgres.
- **Bảng nơi lưu → test:** `ai_outputs` và `edit_events` khi xóa tài khoản chỉ có test Postgres mới. Log đã ghi ra file và log Docker: **chưa có test**.
- **40 client (VT-018):** 12/12 lượt đạt, p95 upload 0,36 đến 0,87 s, 0 lỗi. ffprobe không giải thích được mức chậm của 11-12; mức chậm không tái hiện. Gộp 3 ngày trên `main`: 23/24 lượt đạt.
- **Phản hồi PR:** từ 11-06, 5/23 PR có phản hồi của người khác; 18 PR merge khi chưa có phản hồi.
- **Backend:** có Postgres 16: 459 passed, 0 skipped; không có Postgres: 443 passed, 16 skipped. Ruff sạch.
- **Còn mở:**
  - Nguyên nhân lượt 40 client chậm (fsync Postgres, ghi file audio chưa kiểm).
  - AD-018 247 client p95 ≤ 2,0 s vẫn ✗.
  - Log Docker chưa có test xóa hoặc giới hạn 28 ngày (chỉ xoay vòng theo kích thước).
