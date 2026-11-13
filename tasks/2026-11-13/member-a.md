# 2026-11-13 · Member A: chạy lại E2E trên `main` cuối, kịch bản demo khớp bằng chứng (Đợt 8, đóng băng bằng chứng)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** tối đa 3. Hôm nay **đóng băng bằng chứng**: không thêm tính năng. Chỉ sửa lỗi nếu E2E đỏ, mỗi lỗi một test đỏ trước.
- **Điều kiện bắt đầu:** #53 (A) đã vào `main` ngày 2026-11-13 (`a75853d`, CI xanh 12/12). #54 (B) merge khi CI xanh.
- **Hạn:** mở PR trong ngày 11-13. Ngày 11-14 nộp bài.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## Việc

### 1. [ ] E2E trên `main` có cả #53 và #54 (G0)
- Chạy `npm run e2e` (slow, `retries=0`) trên `main` sau khi #54 vào. PR #53 ghi rõ 24 E2E là của `add08c2`, chưa có sửa progress; lượt này đóng khoảng trống đó.
- Ghi commit, số passed/failed, thời gian vào `docs/evidence/final/frontend-2026-11-13.md`. Đỏ thì giữ log đỏ, không chạy lại cho tới khi xanh rồi chỉ ghi lượt xanh.
- **Message:** `test(frontend): e2e on the final main (G0)`

### 2. [ ] Kịch bản demo khớp bằng chứng (FE-20, VT-018)
- `docs/demo/ux-checklist.md`: thêm luồng tiến độ job dùng 4 ảnh ở `docs/evidence/vt-018/ui/`, và luồng tóm tắt lỗi → "Tạo lại tóm tắt" (sửa ở #53). Mỗi bước ghi ảnh hoặc test chứng minh nó.
- Bước nào không có ảnh hoặc test thì ghi "chưa có bằng chứng".
- **Message:** `docs(demo): demo script tied to the VT-018 progress evidence (FE-20, VT-018)`

### 3. [ ] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong ghi lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-13 member A results (G0)`
