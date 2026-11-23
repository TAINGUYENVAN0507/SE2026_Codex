# 2026-11-23 · Member A: "Xóa bộ lọc" gửi từ khóa cũ, số đếm 0 khi đang tải, thanh phân trang biến mất khi sang trang, E2E trang rỗng (Đợt 13, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #69 (A) và #70 (B) đã vào `main` (`9a87355`, `5c29101`). C review cả hai trước khi merge.
- **Review:** B approve #69 sau 8,0 giờ. A review #70 sau khoảng 63 giờ, quá hạn 18 giờ. Finding P2 của A trên #70 (preflight IPv4) là đúng, C tái hiện được, và nó thành việc 1 của B hôm nay.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-23. Không phụ thuộc PR của B.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [ ] "Xóa bộ lọc" vẫn gửi từ khóa cũ thêm 300 ms (FE-04)
- **Lỗi:** nút "Xóa bộ lọc" (`frontend/src/pages/MeetingListPage.tsx`, khối trạng thái rỗng) gọi `setQuery('')`, `setFilter('all')` và `setPage(1)`, nhưng `search` chỉ về rỗng sau debounce 300 ms. Trong khoảng đó app gửi `GET /meetings?q=<từ khóa cũ>` với bộ lọc "Tất cả", và màn hình vẫn báo "Không tìm thấy cuộc họp".
- **Test đỏ trước** (MSW ghi lại mọi request): gõ từ khóa không khớp, chờ trạng thái rỗng, bấm "Xóa bộ lọc". Kỳ vọng: không có request nào mang từ khóa cũ sau lúc bấm, và request đầu tiên sau lúc bấm không có `q`. Sửa bằng cách đặt `search` về rỗng ngay khi bấm.
- **Message:** `fix(frontend): clearing the filters drops the old search term at once instead of after the debounce (FE-04)`
- **Commit:** _chưa_

### 2. [ ] Đang tải hoặc lỗi mà tiêu đề ghi "0 cuộc họp" (FE-04)
- **Lỗi:** tiêu đề (`total-count`) và chân trang ("Hiển thị 0 trên 0 cuộc họp") dùng `data?.total ?? 0`. Lúc đang tải lần đầu, hoặc khi API lỗi, màn hình khẳng định tài khoản có 0 cuộc họp.
- **Test đỏ trước:** API trả 500. Kỳ vọng không có chữ "0 cuộc họp" và "Hiển thị 0 trên 0"; khối lỗi và nút "Thử lại" vẫn hiện. Lúc đang tải (MSW trễ) cũng không có hai chữ đó.
- **Message:** `fix(frontend): the meeting count is hidden while the list loads or fails instead of showing 0 (FE-04)`
- **Commit:** _chưa_

### 3. [ ] Sang trang thì thanh phân trang biến mất trong lúc tải (FE-04)
- **Lỗi:** `useMeetingsQuery.ts` không giữ dữ liệu cũ khi `queryKey` đổi. Bấm "Trang sau" thì `data` thành `undefined`, nên điều kiện `total > page_size` sai: thanh phân trang biến mất rồi hiện lại khi trang mới về.
- **Test đỏ trước** (MSW trễ trang 2 khoảng 500 ms): sau khi bấm "Trang sau", thanh "Phân trang cuộc họp" vẫn còn, nút "Trang trước" bật, "Trang 2" hiện ngay. Không được làm hỏng test thứ tự phản hồi của 11-17 (phản hồi cũ không ghi đè phản hồi mới), và mutant bỏ `q` khỏi `queryKey` vẫn phải làm test đó đỏ. Ghi lại cả hai lượt chạy.
- **Message:** `fix(frontend): the pagination bar stays while the next page of meetings loads (FE-04)`
- **Commit:** _chưa_

### 4. [ ] E2E trên API thật: trang 2 bị xóa hết thì danh sách về trang 1; bộ lọc trạng thái rỗng báo đúng (FE-04)
- Việc 3 và 4 ngày 11-19 mới chỉ có test MSW. Viết E2E chạy trên API thật với PostgreSQL:
  - Tạo 11 cuộc họp qua API, giữ trạng thái `queued` (`E2E_MANUAL_WORKER=1`), rồi mở trang 2.
  - Xóa cuộc họp duy nhất ở trang 2 qua API. Danh sách đang `queued` nên tự làm mới 5 giây một lần; sau đó phải về trang 1 và không hiện trạng thái rỗng.
  - Bấm bộ lọc "Có lỗi": phải hiện "Không có cuộc họp ở trạng thái này".
- Chạy 3 lượt, `--retries=0`. Log UTF-8 `docs/evidence/final/frontend-empty-page-e2e-2026-11-23.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API returns to page 1 when page 2 is deleted and explains an empty status filter (FE-04)`
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-23 member A results (G0)`
- **Commit:** _chưa_

## Việc chung (không tính commit)

- Review PR ngày 11-23 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub (11-19: review #70 sau khoảng 63 giờ).
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.
