# 2026-11-12 · Member B: backend trên clone sạch với Postgres, bằng chứng xóa dữ liệu và lưu trữ (Đợt 7, đóng băng code)

- **Người làm:** B (`@minhquangha`), nhánh `haquang`.
- **Số commit:** tối đa 5. Hôm nay **đóng băng code**: chỉ sửa lỗi tìm thấy khi kiểm, không thêm tính năng. Không tìm thấy lỗi thì ghi "0 lỗi" và không tạo commit sửa.
- **Điều kiện bắt đầu:** #50 (A) và #51 (B) đã vào `main` (C review diff, CI xanh, merge ngày 2026-11-12, `d9c2d50`). Đợt 6 không còn việc chuyển sang.
- **Hạn:** mở PR trong ngày 11-12. Ngày 11-13 đóng băng bằng chứng.

## Bước 0
```bash
git checkout haquang && git fetch origin && git merge origin/main
```

## Việc

### 1. [x] Backend chạy được từ clone sạch, đủ test cần Postgres (G0)
- Clone mới, làm theo `README.md` và `backend/README.md`: migration, API, worker. Chạy `uv run pytest` hai lần: không có `DATABASE_URL` Postgres (ghi số skipped) và có Postgres 16 (14 test đang skip phải chạy thật).
- Ghi lệnh, commit, passed/skipped của từng lần vào `docs/evidence/final/backend-2026-11-12.md`. README sai thì sửa trong commit này.
- **Commit:** `9f247a9`
- **Message:** `test(backend): clean-clone run with and without Postgres on the frozen main (G0)`

### 2. [x] Bằng chứng xóa dữ liệu cá nhân qua mọi module và log (AD-018)
- Trên Postgres, chạy `test_delete_meeting.py`, `test_delete_user.py`, `tests/privacy/test_privacy_canary.py`. Lưu log vào `docs/evidence/ad-018/deletion-2026-11-12.log`.
- Thêm một bảng ngắn trong `docs/evidence/ad-018/README.md`: mỗi nơi lưu (bảng DB, file audio, artifact, `idempotency_keys`, log) → test nào kiểm nó bị xóa. Nơi nào không có test thì ghi "chưa có test", không viết là đã kiểm.
- **Commit:** `75ecf6f`
- **Message:** `test(backend): deletion evidence across modules and logs on Postgres (AD-018)`

### 3. [x] Bằng chứng lưu trữ 14 và 28 ngày chạy thật (RE-018, AD-018)
- Chạy job retention trên Postgres với dữ liệu tổng hợp có tuổi 13, 14, 15, 27, 28, 29 ngày. Ghi những gì bị xóa và những gì còn lại vào `docs/evidence/final/retention-2026-11-12.md`. Biên không khớp tài liệu thì đó là lỗi: sửa ở việc 4.
- **Commit:** `101fd57`
- **Message:** `test(backend): retention boundaries on Postgres (RE-018, AD-018)`

### 4. Sửa lỗi tìm thấy ở việc 1–3 (chỉ khi có)
- Không tìm thấy lỗi trong việc 1–3 (0 lỗi). Toàn bộ 452 test backend pass trên PostgreSQL 16, 15/15 test xóa dữ liệu và canary pass, các mốc biên lưu trữ 14/28 ngày hoạt động chính xác. Không tạo commit sửa lỗi.

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong ghi lý do, không tick.
- **Commit:** `f9adce1`
- **Message:** `docs(tasks): record 2026-11-12 member B results (G0)`
