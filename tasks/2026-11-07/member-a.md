# 2026-11-07 · Member A: E2E, xóa tài khoản, demo

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** PR #33 (B) và PR #34 (A) đã vào `main`. Làm Bước 0 sau khi cả hai đã merge.
- **Mục tiêu:** E2E phủ đường người quản lý kiểm chứng biên bản; người dùng xóa được cả tài khoản; có kịch bản demo.

Kế hoạch: [`tasks/ROADMAP.md`](../ROADMAP.md), Đợt 2.

## Bước 0

```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Lệnh kiểm tra mỗi commit, trong `frontend/`: `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build && npx playwright test`.

## 5 commit

### 1. [ ] E2E tóm tắt và export trên stack thật (FE-18)
- Meeting `ready`: tóm tắt hiện, bấm evidence thì player tua đúng giây; export TXT/MD/JSON tải về được, không mock.
- **Xong khi:** `frontend/e2e/flows/export.spec.ts` xanh trên CI, không `waitForTimeout` cố định.
- **Message:** `test(frontend): summary evidence and export on the real stack (FE-18)`
- **Hash:**

### 2. [ ] Evidence trong file tải về khớp giao diện (FE-18)
- Đọc file TXT/MD vừa tải, so từng mốc `hh:mm:ss` với link evidence trên giao diện.
- **Xong khi:** E2E khẳng định mỗi ý/action item có mốc tương ứng; ý không có evidence mang nhãn "Chưa có bằng chứng" ở cả hai nơi.
- **Message:** `test(frontend): exported evidence matches what the page shows (FE-18)`
- **Hash:**

### 3. [ ] Giao diện xóa tài khoản (FE-19)
- Cần B xong `DELETE /auth/me` (commit 1 của B hôm nay). Trang cài đặt có nút, hộp xác nhận nêu rõ mọi cuộc họp sẽ bị xóa, gõ lại email để xác nhận.
- **Xong khi:** Vitest cho xác nhận, lỗi 5xx giữ nguyên trang; E2E: xóa xong về trang đăng nhập, đăng nhập lại bằng tài khoản cũ báo sai.
- **Message:** `feat(frontend): delete the account from settings (FE-19)`
- **Hash:**

### 4. [ ] Audio hết hạn: E2E trọn luồng (FE-19)
- Dựng meeting với `retention_until` đã qua + chạy `python -m app.scripts.cleanup`; trang chi tiết báo "Audio đã hết hạn lưu trữ", transcript vẫn đọc được.
- **Xong khi:** E2E xanh trên CI.
- **Message:** `test(frontend): expired audio keeps the transcript readable (FE-19)`
- **Hash:**

### 5. [ ] Checklist UX và kịch bản demo
- `docs/demo/ux-checklist.md`: ảnh chụp thật từ app đang chạy cho upload, tiến độ, tóm tắt có evidence, export, xóa; kịch bản demo 5 phút. Ảnh chỉ dùng dữ liệu mẫu, không audio hay transcript thật.
- **Message:** `docs(demo): UX checklist with screenshots and a 5-minute script (FE-16)`
- **Hash:**

## Cuối ngày
- [ ] Tick và ghi hash. Push `vantuong`, mở PR vào `main`. **Không tự merge.**
