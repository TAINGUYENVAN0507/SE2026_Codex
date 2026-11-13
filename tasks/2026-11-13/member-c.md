# 2026-11-13 · Member C: xóa dữ liệu trên Postgres thật, chẩn đoán lượt 40 client chậm, đóng băng bằng chứng (Đợt 8)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #53 (A) đã vào `main` (C review diff, CI xanh 12/12, merge `a75853d`). B push 4 commit lên `haquang` ngày 11-12 nhưng chưa mở PR; C mở thay (#54) và merge khi CI xanh.
- **Mục tiêu:** ngày cuối trước hạn nộp 11-14. Không đổi code app. Chỉ thêm test, công cụ đo và sửa bằng chứng sai.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [ ] Test xóa cuộc họp và xóa tài khoản trên Postgres đã migrate thật. Khi review #54 thấy `test_delete_meeting.py`, `test_delete_user.py` và `test_privacy_canary.py` cứng `sqlite:///:memory:` và tự viết lại trigger `edit_events`, trong khi `docs/evidence/ad-018/README.md` ghi log "trên PostgreSQL 16". Test mới điền mọi bảng (gồm `jobs`, `ai_outputs`, `edit_events`), chạy hai mutant trên service xóa | `test(backend): erasure on migrated Postgres with every table populated (AD-018, BE-18)` | |
| 2 | [ ] Sửa bằng chứng xóa dữ liệu: log UTF-8 đọc được trên GitHub, bảng nơi lưu → test khớp với assert thật, "chưa có test" ở chỗ chưa có | `docs(evidence): deletion matrix matches the real asserts (AD-018)` | |
| 3 | [ ] Chẩn đoán hai mức thời gian ở 40 client: 6 cặp lượt xen kẽ ffprobe thật / ffprobe giả, cùng `main`, cùng máy | `test(backend): interleaved 40-client runs to isolate the slow mode (VT-018)` | |
| 4 | [ ] Sinh lại thời gian phản hồi PR tới #54; bản đồ bằng chứng và ROADMAP theo `main` cuối (bỏ dòng "chưa" đã lỗi thời về metric stage) | `docs(evidence): final evidence map, PR response times and roadmap (RE-018, AD-018, VT-018)` | |
| 5 | [ ] Tick, hash | `docs(tasks): record 2026-11-13 member C results (G0)` | commit này |

## Kết quả và điều còn mở

(điền khi xong)
