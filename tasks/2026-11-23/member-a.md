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

### 1. [x] "Xóa bộ lọc" vẫn gửi từ khóa cũ thêm 300 ms (FE-04)
- **Lỗi:** nút "Xóa bộ lọc" (`frontend/src/pages/MeetingListPage.tsx`, khối trạng thái rỗng) gọi `setQuery('')`, `setFilter('all')` và `setPage(1)`, nhưng `search` chỉ về rỗng sau debounce 300 ms. Trong khoảng đó app gửi `GET /meetings?q=<từ khóa cũ>` với bộ lọc "Tất cả", và màn hình vẫn báo "Không tìm thấy cuộc họp".
- **Test đỏ trước** (MSW ghi lại mọi request): gõ từ khóa không khớp, chờ trạng thái rỗng, bấm "Xóa bộ lọc". Kỳ vọng: không có request nào mang từ khóa cũ sau lúc bấm, và request đầu tiên sau lúc bấm không có `q`. Sửa bằng cách đặt `search` về rỗng ngay khi bấm.
- **Message:** `fix(frontend): clearing the filters drops the old search term at once instead of after the debounce (FE-04)`
- **Commit:** `10bf7850e9def5363cb1e27c02362db6cdef4825`

### 2. [x] Đang tải hoặc lỗi mà tiêu đề ghi "0 cuộc họp" (FE-04)
- **Lỗi:** tiêu đề (`total-count`) và chân trang ("Hiển thị 0 trên 0 cuộc họp") dùng `data?.total ?? 0`. Lúc đang tải lần đầu, hoặc khi API lỗi, màn hình khẳng định tài khoản có 0 cuộc họp.
- **Test đỏ trước:** API trả 500. Kỳ vọng không có chữ "0 cuộc họp" và "Hiển thị 0 trên 0"; khối lỗi và nút "Thử lại" vẫn hiện. Lúc đang tải (MSW trễ) cũng không có hai chữ đó.
- **Message:** `fix(frontend): the meeting count is hidden while the list loads or fails instead of showing 0 (FE-04)`
- **Commit:** `ae0c8af80a3656297547f9bdbdd0a5ee913a7754`

### 3. [x] Sang trang thì thanh phân trang biến mất trong lúc tải (FE-04)
- **Lỗi:** `useMeetingsQuery.ts` không giữ dữ liệu cũ khi `queryKey` đổi. Bấm "Trang sau" thì `data` thành `undefined`, nên điều kiện `total > page_size` sai: thanh phân trang biến mất rồi hiện lại khi trang mới về.
- **Test đỏ trước** (MSW trễ trang 2 khoảng 500 ms): sau khi bấm "Trang sau", thanh "Phân trang cuộc họp" vẫn còn, nút "Trang trước" bật, "Trang 2" hiện ngay. Không được làm hỏng test thứ tự phản hồi của 11-17 (phản hồi cũ không ghi đè phản hồi mới), và mutant bỏ `q` khỏi `queryKey` vẫn phải làm test đó đỏ. Ghi lại cả hai lượt chạy.
- **Message:** `fix(frontend): the pagination bar stays while the next page of meetings loads (FE-04)`
- **Commit:** `4dc21051eb5e1115ad67a4b3d1ae8239228b0e83`

### 4. [x] E2E trên API thật: trang 2 bị xóa hết thì danh sách về trang 1; bộ lọc trạng thái rỗng báo đúng (FE-04)
- Việc 3 và 4 ngày 11-19 mới chỉ có test MSW. Viết E2E chạy trên API thật với PostgreSQL:
  - Tạo 11 cuộc họp qua API, giữ trạng thái `queued` (`E2E_MANUAL_WORKER=1`), rồi mở trang 2.
  - Xóa cuộc họp duy nhất ở trang 2 qua API. Danh sách đang `queued` nên tự làm mới 5 giây một lần; sau đó phải về trang 1 và không hiện trạng thái rỗng.
  - Bấm bộ lọc "Có lỗi": phải hiện "Không có cuộc họp ở trạng thái này".
- Chạy 3 lượt, `--retries=0`. Log UTF-8 `docs/evidence/final/frontend-empty-page-e2e-2026-11-23.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API returns to page 1 when page 2 is deleted and explains an empty status filter (FE-04)`
- **Commit:** `f4f9ad8cf52079729c5a3a15a0bc766fb805bdc0`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-23 member A results (G0)`
- **Commit:** `commit này`

## Việc chung (không tính commit)

- Review PR ngày 11-23 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub (11-19: review #70 sau khoảng 63 giờ).
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.


## Kết quả thực hiện — 24/11/2026

- Cập nhật vantuong bằng ff-only từ main `6d5f94d` trước khi code. Thực hiện
  phân công 23/11 vào ngày 24/11; chưa mở PR đúng hạn 23/11, không ghi lùi ngày.
- Việc 1: MSW đỏ vì request đầu sau Xóa bộ lọc còn q cũ; sửa search ngay cùng
  query, kiểm mọi request thêm 1 giây. 26 test liên quan đạt sau sửa.
- Việc 2: hai test đỏ cho tải trễ/HTTP 500. Ẩn số đếm khi tải/lỗi, giữ alert/Thử lại;
  response thành công rỗng vẫn hiện 0 đúng. 28 test liên quan đạt.
- Việc 3: test đỏ khi mất thanh phân trang. Giữ placeholder chỉ khi q/status
  không đổi, không tính trang cuối từ placeholder; 29 test liên quan đạt.
  Mutant bỏ q khỏi queryKey bị test thứ tự phản hồi phát hiện; khôi phục nguyên
  byte và chạy lại đủ 12 test search đạt. Log đỏ vẫn giữ.
- Việc 4: 3/3 lượt E2E Chromium trên API/PostgreSQL 16 thật, ba database mới,
  retries=0, không skip/pageerror. Mỗi lượt tạo 11 queued, xóa mục trang 2,
  poll tự về trang 1 với 10 mục; Có lỗi hiện đúng thông báo. finally xóa đủ
  mục/user riêng. Dọn container QA; cổng 14173/18000/55463 không còn lắng nghe.
- Gate cuối: lint, format:check, typecheck, npm test, test:coverage, build đạt.
  **323 test/54 file, 0 failed, 0 skipped.** Coverage lines 86.96%, branches 82.40%,
  giữ floors 84.53%/79.11%. Không chạy model AI hoặc dùng audio thật.
- Evidence UTF-8 tại docs/evidence/final/: `frontend-clear-filter-*`,
  `frontend-list-counts-*`, `frontend-pagination-*`,
  `frontend-empty-page-e2e-2026-11-23.{log,json}` và ba JSON từng lượt,
  `frontend-gates-2026-11-23.{log,json}`. Ngày tên file theo phân công;
  metadata ghi thời điểm chạy thật. Chi tiết hành vi/test: docs/frontend/FE-04.md.

### Chờ sau phần local

- Khoảng 09:42 ngày 24/11 (+07), GitHub không có PR mở; review PR ngày 23/11
  của B chưa thực hiện vì chưa có PR. Khi B mở, review/comment trong 18 giờ.
- Chưa có nhận xét mới trên PR của đợt này vì chưa mở PR.
- Chưa push/mở PR đợt này; chờ người dùng cho phép. CI GitHub và merge chưa
  xác nhận. Không tự merge. Tick phía trên ghi phần triển khai/kiểm tra local,
  chưa có nghĩa hoàn tất Definition of Done trên main.
