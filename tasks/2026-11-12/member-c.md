# 2026-11-12 · Member C: test do AI sinh cho retry và hàng đợi job, đo bằng mutation, bỏ hoặc sửa test yếu; số đo cuối cho VT-018 (Đợt 7)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen-vt018-ai-tests` (VT-018 yêu cầu nhánh riêng).
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #50 và #51 đã vào `main` (C review diff, CI xanh 12/12 và 15/15, merge ngày 2026-11-12, `d9c2d50`).
- **Mục tiêu:** VT-018 yêu cầu AI sinh test và sinh viên xóa hoặc sửa ít nhất 2 test yếu. Repo chưa có phần này. Hôm nay đóng băng code: chỉ thêm test và công cụ đo, không đổi code app.

| # | Việc | Message | Hash |
|---|---|---|---|
| 1 | [ ] Prompt và plan của AI, lưu nguyên văn, commit **trước** khi có test | `docs(evidence): AI prompt and raw plan for generated retry tests (VT-018)` | |
| 2 | [ ] Test AI sinh, giữ nguyên bản thô, kèm log chạy | `test(backend): raw AI-generated tests for job retry and queue (VT-018)` | |
| 3 | [ ] Ma trận mutation: mỗi test AI giết được mutant nào; test không giết mutant nào hoặc assert yếu là ứng viên test yếu | `test(backend): mutation matrix for the AI-generated tests (VT-018)` | |
| 4 | [ ] Xóa hoặc sửa ít nhất 2 test yếu, chạy lại ma trận để có số trước và sau | `test(backend): drop or fix weak AI-generated tests, with before/after mutation results (VT-018)` | |
| 5 | [ ] Số đo cuối trên `main` đã đóng băng: tải 40 client 3 lượt, coverage bộ VT-018; bản đồ bằng chứng, ROADMAP, tick và hash | `docs(evidence): final VT-018 numbers on the frozen main and member C record (VT-018, G0)` | |
