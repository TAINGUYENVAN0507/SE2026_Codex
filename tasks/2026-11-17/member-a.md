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

### 1. [ ] E2E trên API thật: tìm bằng `%` và `_` chỉ ra tiêu đề chứa đúng ký tự đó (FE-04, BE-05)
- **Lý do:** từ #64 ô tìm gửi `q` lên API. `meetings.py:145` ghép `q` vào `ilike(f"%{q}%")` mà không escape, nên `%` và `_` là ký tự đại diện: gõ `%` ra mọi cuộc họp, gõ `_` ra mọi tiêu đề có từ 1 ký tự trở lên. Trước #64 lỗi này không lộ vì lọc ở trình duyệt.
- **Làm:** tạo 3 cuộc họp qua API thật (PostgreSQL) với tiêu đề `Giảm 100% chi phí`, `Họp_nhóm`, `Họp nhóm`. Gõ `%` phải ra đúng 1, gõ `_` phải ra đúng 1 (không phải 2), gõ `100%` ra 1. Test đỏ trên `main` hiện tại; log đỏ `docs/evidence/final/frontend-search-wildcard-red-2026-11-17.log`.
- Test xanh sau khi PR của B vào `main`; ghi rõ thứ tự trong PR.
- **Message:** `test(frontend): e2e search treats % and _ as literal characters on the real API (FE-04)`
- **Commit:** _chưa_

### 2. [ ] Tìm kiếm lỗi mạng hoặc 500: danh sách báo lỗi, giữ từ khóa đã gõ, có nút thử lại (FE-04)
- Test MSW: `GET /meetings?q=...` trả 500, rồi trả 200 sau khi bấm thử lại. Từ khóa trong ô tìm không bị xóa; không hiện "Không tìm thấy cuộc họp" khi thực ra là lỗi.
- Nếu đã đúng thì chỉ thêm test (ghi "không có lỗi"); nếu sai thì test đỏ trước rồi sửa.
- **Message:** `test(frontend): meeting search keeps the typed text and shows an error with retry on failure (FE-04)`
- **Commit:** _chưa_

### 3. [ ] Phản hồi cũ không ghi đè phản hồi mới (FE-04)
- Test: gõ `a`, chờ 300 ms, gửi; gõ `ab`, chờ 300 ms, gửi. Phản hồi của `a` về **sau** phản hồi của `ab` (trễ 1 s). Danh sách và dòng "Hiển thị n trên N" phải theo `ab`.
- Có kèm mutant: thử bỏ `q` khỏi `queryKey` (`useMeetingsQuery.ts`) và cho thấy test đỏ, rồi khôi phục. Log mutant UTF-8.
- **Message:** `test(frontend): a late response for an older search term does not replace the newer one (FE-04)`
- **Commit:** _chưa_

### 4. [ ] Đổi bộ lọc trạng thái khi đang ở trang 2 của kết quả tìm kiếm (FE-04)
- Hiện `filter` và `search` đổi thì `page` có về 1 không? Đọc `MeetingListPage.tsx`; nếu không, kết quả có thể rỗng dù có dữ liệu. Test đỏ trước nếu lỗi: 12 cuộc họp khớp `q`, ở trang 2, bấm bộ lọc "Đã xong".
- **Message:** `fix(frontend): changing the status filter returns the meeting list to page 1 (FE-04)`
- Nếu không có lỗi, commit chỉ thêm test, đổi tiền tố thành `test(frontend)`.
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test.
- **Message:** `docs(tasks): record 2026-11-17 member A results (G0)`
- **Commit:** commit này

## Việc chung (không tính commit)

- Review PR ngày 11-17 của B trong 18 giờ kể từ lúc B mở, ghi comment trên GitHub.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.
