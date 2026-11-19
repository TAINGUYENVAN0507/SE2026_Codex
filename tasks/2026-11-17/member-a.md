# 2026-11-17 · Member A: tìm cuộc họp với ký tự đặc biệt, lỗi và thứ tự phản hồi của ô tìm kiếm (Đợt 11, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #61 (B) và #64 (A) đã vào `main` (`8fcf72e`, `1dc6b5c`), CI xanh 18/18 và 15/15. C review diff cả hai trước khi merge.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-17. **PR của A merge sau PR của B**: việc 1 cần sửa backend của B (việc 1 của B).

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [x] E2E trên API thật: tìm bằng `%` và `_` chỉ ra tiêu đề chứa đúng ký tự đó (FE-04, BE-05)
- **Lý do:** từ #64 ô tìm gửi `q` lên API. `meetings.py:145` ghép `q` vào `ilike(f"%{q}%")` mà không escape, nên `%` và `_` là ký tự đại diện: gõ `%` ra mọi cuộc họp, gõ `_` ra mọi tiêu đề có từ 1 ký tự trở lên. Trước #64 lỗi này không lộ vì lọc ở trình duyệt.
- **Làm:** tạo 3 cuộc họp qua API thật (PostgreSQL) với tiêu đề `Giảm 100% chi phí`, `Họp_nhóm`, `Họp nhóm`. Gõ `%` phải ra đúng 1, gõ `_` phải ra đúng 1 (không phải 2), gõ `100%` ra 1. Test đỏ trên `main` hiện tại; log đỏ `docs/evidence/final/frontend-search-wildcard-red-2026-11-17.log`.
- Test xanh sau khi PR của B vào `main`; ghi rõ thứ tự trong PR.
- **Message:** `test(frontend): e2e search treats % and _ as literal characters on the real API (FE-04)`
- **Commit:** `a140c15c5fe1b2e2a6d828fc0a0b9dea367c59dc`

### 2. [x] Tìm kiếm lỗi mạng hoặc 500: danh sách báo lỗi, giữ từ khóa đã gõ, có nút thử lại (FE-04)
- Test MSW: `GET /meetings?q=...` trả 500, rồi trả 200 sau khi bấm thử lại. Từ khóa trong ô tìm không bị xóa; không hiện "Không tìm thấy cuộc họp" khi thực ra là lỗi.
- Nếu đã đúng thì chỉ thêm test (ghi "không có lỗi"); nếu sai thì test đỏ trước rồi sửa.
- **Message:** `test(frontend): meeting search keeps the typed text and shows an error with retry on failure (FE-04)`
- **Commit:** `3aee8b36f8bba341cde209ccf472853da586aced`

### 3. [x] Phản hồi cũ không ghi đè phản hồi mới (FE-04)
- Test: gõ `a`, chờ 300 ms, gửi; gõ `ab`, chờ 300 ms, gửi. Phản hồi của `a` về **sau** phản hồi của `ab` (trễ 1 s). Danh sách và dòng "Hiển thị n trên N" phải theo `ab`.
- Có kèm mutant: thử bỏ `q` khỏi `queryKey` (`useMeetingsQuery.ts`) và cho thấy test đỏ, rồi khôi phục. Log mutant UTF-8.
- **Message:** `test(frontend): a late response for an older search term does not replace the newer one (FE-04)`
- **Commit:** `346e40612846e6703075f927552b6f63302ca0a9`

### 4. [x] Đổi bộ lọc trạng thái khi đang ở trang 2 của kết quả tìm kiếm (FE-04)
- Hiện `filter` và `search` đổi thì `page` có về 1 không? Đọc `MeetingListPage.tsx`; nếu không, kết quả có thể rỗng dù có dữ liệu. Test đỏ trước nếu lỗi: 12 cuộc họp khớp `q`, ở trang 2, bấm bộ lọc "Đã xong".
- **Message:** `fix(frontend): changing the status filter returns the meeting list to page 1 (FE-04)`
- Nếu không có lỗi, commit chỉ thêm test, đổi tiền tố thành `test(frontend)`.
- **Commit:** `3bf0fab71303a60dd865ab289f9975ae6624e920`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test.
- **Message:** `docs(tasks): record 2026-11-17 member A results (G0)`
- **Commit:** commit này

## Việc chung (không tính commit)

- Review PR ngày 11-17 của B trong 18 giờ kể từ lúc B mở, ghi comment trên GitHub.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.

## Kết quả local — 17/11/2026

- Việc 1 đã viết E2E và chạy đỏ trên API/PostgreSQL 16 thật, retries=0. Ba
  tiêu đề được tạo qua API; seed có sẵn 1 fixture. % và _ trả 4 mục, 100% trả
  1 mục; 0 pageerror. Lượt setup đầu đếm thiếu fixture được giữ log riêng.
  Rà cuối dùng locator chờ đúng href để tránh đọc UI cũ khi đổi q. **Chưa tick
  việc 1** vì cần chạy xanh sau khi PR B sửa escape vào main.
- Việc 2 không có lỗi sản phẩm: thêm 2 test cho HTTP 500 và lỗi mạng,
  giữ từ khóa, alert đúng, Thử lại trả kết quả; không có empty giả.
- Việc 3 gửi a rồi ab cách debounce 300 ms, a trễ 1 giây. Response về ab rồi a,
  UI/footer vẫn theo ab. Mutant bỏ q khỏi queryKey làm test đỏ; khôi phục nguyên
  byte, bộ danh sách đạt 9 test ở thời điểm commit 3.
- Việc 4 không có lỗi sản phẩm: 12 mục khớp q, ở trang 2 rồi lọc Hoàn thành
  trả đúng 7 ready tại trang 1, giữ q. Bộ danh sách cuối đạt **10 test**.
- Việc 5 chạy lint, typecheck, format, toàn bộ Vitest có coverage và build đạt:
  **315 passed / 54 files / 0 skipped**. Coverage statements 84.51%, branches
  82.18%, functions 80.87%, lines 86.91%. Đây là kết quả unit/component;
  E2E wildcard còn đỏ được ghi riêng, chưa tính là đạt.

Kiểm UTF-8 tài liệu đạt 2 test. Đã dừng stack E2E, dọn container PostgreSQL
QA của A và file mật khẩu seed tạm.

Bằng chứng UTF-8 trong docs/evidence/final:

- frontend-search-wildcard-red-2026-11-17.log, bản setup-red và final-red,
  frontend-search-wildcard-2026-11-17.json ghi rõ từng lượt/source.
- frontend-search-errors-2026-11-17.log.
- frontend-search-order-mutant-2026-11-17.log và bản green. Hai test không
  được chọn trong lượt mutant do chạy -t, không phải skip trong suite cuối.
- frontend-search-filter-page-2026-11-17.log.
- frontend-final-*-2026-11-17.log, frontend-gates-2026-11-17.json.

### Còn chờ

- B sửa escape %, _ và \ ở backend rồi PR được merge vào main; khi đó cập
  nhật nhánh A và chạy lại E2E wildcard để có bằng chứng xanh mới tick việc 1.
- Lúc kiểm cuối chưa có PR mở mới của B. Review PR ngày 17/11 của B trong 18
  giờ kể từ lúc mở và trả lời review của PR A khi có.
- Theo yêu cầu của A, đẩy phần đã làm và mở PR để nhóm trưởng review cùng
  PR backend của B. Ghi rõ E2E wildcard đang chờ bản sửa backend và lượt xanh
  trên mã đã tích hợp. Việc 1 tiếp tục để chưa tick. PR chuẩn bị ở dạng Draft
  theo rules/git-workflow.md vì phần kiểm E2E vẫn đang thực hiện.


## Bổ sung ngày 19/11 — hoàn tất việc 1

PR #67 và #66 đã merge. A tự chạy E2E wildcard **3/3 lượt đạt** trên main
3a899b3, mỗi lượt một database PostgreSQL 16 e2e mới, retries=0. %, _ và 100%
trả đúng 1 mục; 0 pageerror. Bằng chứng frontend-search-wildcard-green-2026-11-19.log,
JSON cùng tên và ba wildcard-result r1/r2/r3 trong docs/evidence/final/.
Hash commit đóng việc ghi tại tasks/2026-11-19/member-a.md, việc 1 (commit này).
Các phần trạng thái chờ phía trên là ghi nhận tại thời điểm 17/11.
