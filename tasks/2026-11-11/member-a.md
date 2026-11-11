# 2026-11-11 · Member A: mọi trang đọc dữ liệu chịu được API bận, test mới không flaky (Đợt 6)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #47 và #48 đã vào `main` (C merge ngày 2026-11-11, `1f9d1ca`). Không còn việc chuyển từ 11-10: cả 10 ô đã tick.
- **Hạn:** mở PR trong ngày 11-11. Ngày 11-12 **đóng băng code**, chỉ còn sửa lỗi. Xem [`tasks/ROADMAP.md`](../ROADMAP.md), mục Lịch tới hạn nộp.
- **Mục tiêu:** #47 xử lý 503 ở upload, poll job và các thao tác sửa. Các query đọc dữ liệu khác (danh sách cuộc họp, chi tiết, transcript, tóm tắt) vẫn theo mặc định ở `frontend/src/app/AppProviders.tsx`: `retry: 1` thử lại **ngay**, bỏ qua `Retry-After`, và thử lại cả lỗi 4xx. Ngoài ra cần chứng minh các test mới của #47 không flaky (VT-018).

Kiểm tra trong `frontend/`: `npm run lint && npm run typecheck && npm run test:coverage && npm run build`. Kết quả của C khi gộp thử #47 và #48: 284/284 test, lines 86,53 %, branches 81,11 %.

## Review (không bắt buộc, không tính commit)
Nhóm trưởng tự review diff, chờ CI xanh rồi merge.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## 5 commit

### 1. [ ] Query đọc dữ liệu chỉ thử lại khi API bận hoặc mất mạng, chờ theo `Retry-After` (AD-018, FE-16)
- Trong `AppProviders.tsx`, `retry` chỉ áp dụng cho `ApiError` có `status === 503` hoặc `code === 'NETWORK_ERROR'`, tối đa 2 lần. `retryDelay` lấy `error.retryAfterMs`, nếu không có thì 2 s. Lỗi 4xx (401, 403, 404, 422) không thử lại.
- `useJobQuery` đã tự đặt `retry: false`, nên không bị đổi hành vi.
- Test **đỏ trước** (fake timer + MSW): 503 kèm `Retry-After: 3` rồi 200 thì request thứ hai đi sau 3 s; 404 thì chỉ có 1 request.
- **Message:** `fix(frontend): queries retry only busy or offline responses, after Retry-After (AD-018)`

### 2. [ ] Trang danh sách và trang chi tiết: hết lượt thử thì hiện "máy chủ đang bận" và nút thử lại (AD-018, FE-16)
- Đọc lại `MeetingsPage` và `MeetingDetailPage` (hoặc tên tương ứng trong `src/pages/`). Khi query lỗi 503 sau khi hết lượt thử, hiện thông báo tiếng Việt và nút "Thử lại" gọi `refetch()`. Không hiện trang trắng hay skeleton mãi.
- Nếu trang nào đã làm đúng thì ghi vào thân commit và chỉ thêm test cho trang đó.
- Test MSW cho cả hai trang: 503 liên tục thì thấy nút; bấm nút khi API đã trả 200 thì thấy dữ liệu.
- **Message:** `fix(frontend): meeting list and detail show a busy state with retry (AD-018)`

### 3. [ ] Thông báo bận được trình đọc màn hình đọc lên (FE-16)
- Các thông báo "máy chủ đang bận" của #47 (upload, poll, sửa) và của commit 2 nằm trong vùng `role="status"` hoặc `aria-live="polite"`. Lỗi chặn thao tác dùng `role="alert"`. Focus không nhảy khi thông báo hiện ra.
- Test bằng `getByRole('status')` hoặc `getByRole('alert')` cho từng chỗ.
- **Message:** `fix(frontend): busy notices are announced to screen readers (FE-16)`

### 4. [ ] Test mới của #47 không flaky: chạy lặp và ghi số thật (VT-018)
- Chạy `npx vitest run src/pages/BusyUpload.test.tsx src/features/jobs/BusyPolling.test.tsx src/features/meetings/BusyEdits.test.tsx src/features/audio/uploadBusyTimer.test.ts src/features/jobs/JobTimes.test.tsx` 20 lần liên tiếp, và `npm run e2e` 3 lần. Ghi số lần fail thật vào `docs/evidence/vt-018/flaky-frontend-2026-11-11.md`, kèm lệnh và commit đã chạy.
- Có test fail thì tìm nguyên nhân rồi sửa trong cùng commit, ghi log đỏ trước. Không có thì ghi 0/20, không thêm gì khác.
- **Message:** `test(frontend): repeat the busy-state tests to show they are not flaky (VT-018)`

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong thì ghi "chuyển sang 11-12 (chỉ nếu là sửa lỗi)" và lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-11 member A results (G0)`
