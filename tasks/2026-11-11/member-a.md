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

### 1. [x] Query đọc dữ liệu chỉ thử lại khi API bận hoặc mất mạng, chờ theo `Retry-After` (AD-018, FE-16)

**Kết quả local 11/11:** 9 test MSW + fake timer đỏ trước sửa, xanh sau; 503 có Retry-After=3 thì request kế tiếp đúng sau 3 giây, tối đa 2 retry, fallback 2 giây; 401/403/404/422/500 và lỗi lập trình chỉ một request. useJobQuery giữ retry false.

**Commit:** `c937d0f61660559b9e61f85b28c3558948bf3b9c`.

- Trong `AppProviders.tsx`, `retry` chỉ áp dụng cho `ApiError` có `status === 503` hoặc `code === 'NETWORK_ERROR'`, tối đa 2 lần. `retryDelay` lấy `error.retryAfterMs`, nếu không có thì 2 s. Lỗi 4xx (401, 403, 404, 422) không thử lại.
- `useJobQuery` đã tự đặt `retry: false`, nên không bị đổi hành vi.
- Test **đỏ trước** (fake timer + MSW): 503 kèm `Retry-After: 3` rồi 200 thì request thứ hai đi sau 3 s; 404 thì chỉ có 1 request.
- **Message:** `fix(frontend): queries retry only busy or offline responses, after Retry-After (AD-018)`

### 2. [x] Trang danh sách và trang chi tiết: hết lượt thử thì hiện "máy chủ đang bận" và nút thử lại (AD-018, FE-16)

**Kết quả local 11/11:** Danh sách đã có trạng thái bận/nút nên chỉ thêm test cho trang đó. Chi tiết thêm Thử lại cho cả meeting và transcript, giữ 404 và đường về danh sách. MSW ba ca: list xanh trước, hai detail đỏ trước sửa; sau sửa đều phục hồi từ 503 sang 200.

**Commit:** `1fbc2f34c537bf111107c8e8d56edaf531699b76`.

- Đọc lại `MeetingsPage` và `MeetingDetailPage` (hoặc tên tương ứng trong `src/pages/`). Khi query lỗi 503 sau khi hết lượt thử, hiện thông báo tiếng Việt và nút "Thử lại" gọi `refetch()`. Không hiện trang trắng hay skeleton mãi.
- Nếu trang nào đã làm đúng thì ghi vào thân commit và chỉ thêm test cho trang đó.
- Test MSW cho cả hai trang: 503 liên tục thì thấy nút; bấm nút khi API đã trả 200 thì thấy dữ liệu.
- **Message:** `fix(frontend): meeting list and detail show a busy state with retry (AD-018)`

### 3. [x] Thông báo bận được trình đọc màn hình đọc lên (FE-16)

**Kết quả local 11/11:** Status/polite cho poll còn progress; alert cho lỗi chặn. Test tăng kiểm role/focus ở upload, poll, transcript, speaker, summary/retry job/xóa và hai trang đọc. Khôi phục main landmark trang lỗi; axe tìm ra contrast 3.82:1 ở thông báo list rồi sửa. Sáu view Chromium desktop/mobile sau sửa 0 violation, không tràn ngang; chưa kiểm screen reader thật.

**Commit:** `986e2b8d9e6eb74d14b06646c5f85b73167995d3`.

- Các thông báo "máy chủ đang bận" của #47 (upload, poll, sửa) và của commit 2 nằm trong vùng `role="status"` hoặc `aria-live="polite"`. Lỗi chặn thao tác dùng `role="alert"`. Focus không nhảy khi thông báo hiện ra.
- Test bằng `getByRole('status')` hoặc `getByRole('alert')` cho từng chỗ.
- **Message:** `fix(frontend): busy notices are announced to screen readers (FE-16)`

### 4. [x] Test mới của #47 không flaky: chạy lặp và ghi số thật (VT-018)

**Kết quả local 11/11:** Đúng năm file được giao, 18 test/lượt: 20 lượt liên tiếp 0/20 lỗi. npm run e2e mặc định slow: 24 test/lượt, 3 lượt liên tiếp 0/3 lỗi. Source commit và mọi exit code/hash log có trong báo cáo; không coi số lần thực thi là số test khác nhau. Không sửa/thêm code chỉ để tăng lượt pass.

**Commit:** `6fd2908c822c8581d7c73d4b36b33f089130a967`.

- Chạy `npx vitest run src/pages/BusyUpload.test.tsx src/features/jobs/BusyPolling.test.tsx src/features/meetings/BusyEdits.test.tsx src/features/audio/uploadBusyTimer.test.ts src/features/jobs/JobTimes.test.tsx` 20 lần liên tiếp, và `npm run e2e` 3 lần. Ghi số lần fail thật vào `docs/evidence/vt-018/flaky-frontend-2026-11-11.md`, kèm lệnh và commit đã chạy.
- Có test fail thì tìm nguyên nhân rồi sửa trong cùng commit, ghi log đỏ trước. Không có thì ghi 0/20, không thêm gì khác.
- **Message:** `test(frontend): repeat the busy-state tests to show they are not flaky (VT-018)`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong thì ghi "chuyển sang 11-12 (chỉ nếu là sửa lỗi)" và lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-11 member A results (G0)`

## Tổng kiểm tra local — 11/11/2026

- Nhánh `vantuong` đã fast-forward main `dec1017` trước khi code; #47/#48/#49
  đã vào main. Không còn task cũ chuyển sang. Không đổi tên Biên bản.
- Hoàn thành phần triển khai/kiểm chứng local của 5 mục. Có đúng 5 commit
  theo phân công; hash mục 5 là **commit này** (không tạo commit tự tham chiếu).
- Lint, format, TypeScript, 296 Vitest/48 file dưới coverage và production build
  đạt. Coverage 86.65% lines, 81.34% branches; floors 84.53/79.11 không hạ.
- Nhóm unit 20 lượt, E2E slow 3 lượt; không skip hoặc dùng retry của Playwright
  để che lỗi. Không chạy lại toàn ma trận lỗi ba lần rồi gọi là yêu cầu hôm nay.
- [Hành vi/query](../../docs/frontend/query-busy-2026-11-11.md),
  [browser axe](../../docs/frontend/accessibility-busy-2026-11-11.json),
  [coverage](../../docs/frontend/coverage-2026-11-11.json),
  [báo cáo chạy lặp](../../docs/evidence/vt-018/flaky-frontend-2026-11-11.md).
- Chỉ ảnh và HTTP/audio/DB tổng hợp; không đánh giá AI thật. Cảnh báo native
  Windows os.killpg được ghi đúng trong báo cáo, chưa sửa pipeline C và không
  dùng UI pass để khẳng định cleanup subprocess đã đúng trên mọi nền tảng.
- Database/container và các server do QA tạo đã dừng/dọn; không dừng dịch vụ
  của người dùng. Log/trace/report/ảnh riêng vẫn ngoài Git.
- Chưa push, chưa mở PR, chưa merge; chưa có kết quả CI cho commit ngày 11/11.
  Các ô tick xác nhận công việc local, không thay điều kiện CI/review/merge
  trong Definition of Done. Review thành viên là tùy chọn theo phân công.
