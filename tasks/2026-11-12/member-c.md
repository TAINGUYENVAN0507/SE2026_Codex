# 2026-11-12 · Member C: test do AI sinh cho retry và hàng đợi job, đo bằng mutation, bỏ hoặc sửa test yếu; số đo cuối cho VT-018 (Đợt 7)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen-vt018-ai-tests` (VT-018 yêu cầu nhánh riêng).
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #50 và #51 đã vào `main` (C review diff, CI xanh 12/12 và 15/15, merge ngày 2026-11-12, `d9c2d50`).
- **Mục tiêu:** VT-018 yêu cầu AI sinh test và sinh viên xóa hoặc sửa ít nhất 2 test yếu. Repo chưa có phần này. Hôm nay đóng băng code: chỉ thêm test và công cụ đo, không đổi code app.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [x] Prompt và plan của AI, lưu nguyên văn, commit **trước** khi có test | `docs(evidence): AI prompt and raw plan for generated retry tests (VT-018)` | `6c764ba` |
| 2 | [x] Test AI sinh, giữ nguyên bản thô, kèm log chạy | `test(backend): raw AI-generated tests for job retry and queue (VT-018)` | `1ed5df0` |
| 3 | [x] Ma trận mutation: mỗi test AI giết được mutant nào; test không giết mutant nào hoặc assert yếu là ứng viên test yếu | `test(backend): mutation matrix for the AI-generated tests (VT-018)` | `a045ed7` |
| 4 | [x] Xóa hoặc sửa ít nhất 2 test yếu, chạy lại ma trận để có số trước và sau | `test(backend): drop or fix weak AI-generated tests, with before/after mutation results (VT-018)` | `3617a0b` |
| 5 | [x] Số đo cuối trên `main` đã đóng băng: tải 40 client 6 lượt (3 theo kế hoạch, thêm 3 sau khi lượt 2 không đạt), coverage bộ VT-018; bản đồ bằng chứng, ROADMAP, tick và hash | `docs(evidence): final VT-018 numbers on the frozen main and member C record (VT-018, G0)` | commit này |

## Kết quả và điều còn mở

Ngoài 5 commit: `d6138ee` (giao việc). Trước đó C review diff và merge #51 (B) và #50 (A) khi CI xanh hết.

- **AI sinh test (VT-018):**
  - Plan được commit trước khi có test.
  - Bản thô: 45 test, 1 test sai (fail trên code đúng), giết 18/24 mutant.
  - Sửa 4, xóa 5, thêm 1. Bản review: 42 test, giết 24/24 mutant, chạy lặp 20/20 lần đều pass. 24/24 không phải phép đo độc lập: khi sửa test đã biết trước mutant nào sống (`docs/evidence/vt-018/ai-tests/04-review.md`).
  - Coverage và mutation lệch nhau: `retry.py` 100 % coverage mà vẫn có mutant sống.
- **40 client trên `main` đã đóng băng: 5/6 lượt đạt, 1/6 không đạt** (p95 upload 1,56 s, 0 lỗi).
  - Kết quả chia hai mức, quanh 0,5 s và quanh 1,4 đến 1,6 s. Thời gian nằm trong app; nguyên nhân chưa rõ.
  - Trạng thái VT-018 về tải đổi từ ✓ sang ◐.
- **Coverage bộ VT-018:** `queue.py`, `reaper.py`, `retry.py`, `job.py` đạt 100 %, 113 passed.
- **Backend:** 443 passed, 14 skipped, ruff sạch.
- **Còn mở:**
  - Bước 0 của BT3 (bác bỏ ≥ 2 điểm của plan bằng bằng chứng) và reflection là phần của người dùng.
  - Nguyên nhân lượt 40 client chậm chưa tìm ra.
  - AD-018 247 vẫn ✗.
