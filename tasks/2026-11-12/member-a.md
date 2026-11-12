# 2026-11-12 · Member A: kiểm frontend trên clone sạch, bằng chứng giao diện tiến độ cho VT-018 (Đợt 7, đóng băng code)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** tối đa 5. Hôm nay **đóng băng code**: chỉ sửa lỗi tìm thấy khi kiểm, không thêm tính năng. Không tìm thấy lỗi thì ghi "0 lỗi" và không tạo commit sửa.
- **Điều kiện bắt đầu:** #50 (A) và #51 (B) đã vào `main` (C review diff, CI xanh, merge ngày 2026-11-12, `d9c2d50`). Đợt 6 không còn việc chuyển sang.
- **Hạn:** mở PR trong ngày 11-12. Ngày 11-13 đóng băng bằng chứng.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## Việc

### 1. [ ] Frontend chạy được từ clone sạch (G0)
- `git clone` vào thư mục mới, làm đúng theo `README.md` và `frontend/README.md`. Chạy `npm ci && npm run lint && npm run typecheck && npm run test:coverage && npm run build && npm run e2e`.
- Ghi lệnh, commit, số test, coverage lines/branches và mọi bước README sai hoặc thiếu vào `docs/evidence/final/frontend-2026-11-12.md`. README sai thì sửa luôn trong commit này.
- **Message:** `test(frontend): clean-clone run on the frozen main (G0)`

### 2. [ ] Ảnh giao diện tiến độ cho VT-018 (FE-20, VT-018)
- Playwright với fake pipeline, chụp 4 ảnh vào `docs/evidence/vt-018/ui/`: job `queued`, `running` ở giữa chừng (có %), `succeeded` (có thời gian bắt đầu và kết thúc), và sau khi bấm chạy lại một job `failed` (tiến độ bắt đầu lại, không có segment trùng trên trang transcript).
- Chỉ dữ liệu tổng hợp. Ghi lệnh tạo ảnh và commit trong `docs/evidence/vt-018/ui/README.md`.
- **Message:** `test(frontend): progress screenshots for the async job flow (VT-018)`

### 3. [ ] Bấm "Chạy lại" hai lần không tạo hai job (VT-018, FE-20)
- Test MSW: bấm nhanh hai lần nút chạy lại job failed thì chỉ có 1 `POST` (hoặc 2 `POST` với cùng `Idempotency-Key`). Đỏ thì sửa trong commit này, ghi log đỏ trước khi sửa.
- **Message:** `test(frontend): double-clicking retry starts one job (VT-018)`

### 4. [ ] Sửa lỗi tìm thấy ở việc 1–3 (chỉ khi có)
- Mỗi lỗi một test đỏ trước. Không có lỗi thì không tạo commit, ghi "0 lỗi" ở việc 5.
- **Message:** `fix(frontend): <lỗi> (G0)`

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong ghi lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-12 member A results (G0)`
