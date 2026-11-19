# 2026-11-19 · Member A: ô tìm và giới hạn 200 ký tự, trang rỗng, trạng thái rỗng theo bộ lọc (Đợt 12, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #67 (B) rồi #66 (A) đã vào `main` (`efbbed9`, `006fd8c`). C review cả hai trước khi merge. C chạy E2E wildcard của A trên #66 gộp với `main` (có #67): 3/3 passed, `retries=0` (comment review trên #66).
- **Review:** B review #66 sau khoảng 31 giờ (quá hạn 18 giờ). A chưa review #67 của B.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-19. Không phụ thuộc PR của B, merge theo thứ tự xanh CI.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [x] E2E wildcard xanh trên `main`, tick việc 1 ngày 11-17 (FE-04, BE-05)
- Chạy `search-wildcard.spec.ts` (`playwright.evidence.config.ts`, `--retries=0`) **3 lượt** trên `main` sau #66, mỗi lượt một database e2e mới. Log UTF-8: `docs/evidence/final/frontend-search-wildcard-green-2026-11-19.log`, kèm `wildcard-result.json` của từng lượt.
- Tick việc 1 trong `tasks/2026-11-17/member-a.md`, ghi hash commit này và số lượt.
- **Message:** `test(frontend): e2e wildcard search is green on main after #67 (FE-04)`
- **Commit:** `7e52573ef6e05ca6de8a1b9b956804b701527934`

### 2. [x] Ô tìm cho gõ quá 200 ký tự, API trả 422 từ #67 (FE-04)
- **Lỗi:** từ #67, `GET /meetings` có `q` `max_length=200`. Ô `aria-label="Tìm cuộc họp"` (`frontend/src/pages/MeetingListPage.tsx:83`) không có `maxLength`: dán 250 ký tự, danh sách chuyển sang "Không tải được cuộc họp".
- **Test đỏ trước** (MSW trả 422 khi `q` dài hơn 200): dán 250 ký tự, request gửi đi có `q` đúng 200 ký tự, danh sách vẫn hiện. Sửa bằng `maxLength={200}` (đặt hằng số dùng chung, ghi chú dẫn tới `meetings.py`).
- **Message:** `fix(frontend): the search box stops at 200 characters, the limit the API accepts since #67 (FE-04)`
- **Commit:** `4ca62d3e3f1fb9140811103aada30af7ea327d53`

### 3. [x] Trang hiện tại trả về rỗng mà `total > 0` (FE-04)
- **Lỗi có thể có:** `page` chỉ về 1 khi đổi bộ lọc hoặc từ khóa. Nếu đang ở trang 2 mà số cuộc họp giảm (xóa ở tab khác, poll làm mới), API trả `items: []`, `total: 10`. Danh sách hiện "Chưa có cuộc họp" và chân trang "Hiển thị 0 trên 10".
- **Test đỏ trước** (MSW): trang 1 trả 10 mục `total: 11`, sang trang 2, rồi trang 2 trả `items: []`, `total: 10`. Kỳ vọng: về trang cuối còn dữ liệu (trang 1), không hiện trạng thái rỗng. Hành vi API của trường hợp này do B khóa ở việc 4 của B.
- **Message:** `fix(frontend): the meeting list goes back to the last page when the current page comes back empty (FE-04)`
- **Commit:** `bbb8669cf77f6ebb105a119a5dd82e2dc895ea16`

### 4. [x] Lọc "Lỗi" không có mục nào nhưng màn hình báo "Chưa có cuộc họp" (FE-04)
- **Lỗi:** `MeetingListPage.tsx:166` chỉ xét `search`. Chọn bộ lọc trạng thái không có cuộc họp nào thì hiện "Chưa có cuộc họp / Tạo cuộc họp mới để bắt đầu", dù tài khoản có cuộc họp ở trạng thái khác.
- **Test đỏ trước:** bộ lọc `failed`, API trả rỗng. Kỳ vọng tiêu đề "Không có cuộc họp ở trạng thái này" và nút "Xóa bộ lọc". Không bộ lọc, không từ khóa thì vẫn "Chưa có cuộc họp".
- **Message:** `fix(frontend): an empty status filter says no meeting has that status instead of no meeting at all (FE-04)`
- **Commit:** `34aeaac772cb8ed51b20755823a880f97de63734`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-19 member A results (G0)`
- **Commit:** commit này

## Việc chung (không tính commit)

- Review PR ngày 11-19 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub (11-17: A không review #67).
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.


## Kết quả local — 19/11/2026

- Việc 1: **3/3 lượt E2E wildcard đạt** trên main 3a899b3, ba database mới
  PostgreSQL 16, retries=0. %, _ và 100% đều đúng total=1, row/ID/footer và
  0 pageerror. Đã tick việc 1 ngày 17/11 và ghi hash commit hoàn tất.
- Việc 2: regression dán 250 ký tự với MSW 422 đã đỏ trước patch. Thêm
  maxLength từ hằng số MEETING_SEARCH_MAX_LENGTH=200 có dẫn backend;
  sau patch input/request đúng 200 và vẫn có danh sách, không alert.
- Việc 3: regression poll trang 2 từ total=11 về []/total=10 đã đỏ trước patch.
  Tính trang cuối từ total/page_size và chỉnh page trước khi commit UI.
  Kiểm thêm trang 3 với 25 mục giảm còn 15, về đúng trang 2 và hiện 5 mục.
- Việc 4: regression bộ lọc Có lỗi rỗng đã đỏ trước patch. Hiện thông báo
  Không có cuộc họp ở trạng thái này và nút Xóa bộ lọc; xóa lọc lấy lại dữ liệu.
  Trạng thái tài khoản rỗng/tìm không ra vẫn được kiểm bằng bộ test cũ.
- Việc 5: lint, TypeScript, format, production build và Vitest có coverage đều
  đạt. **319 passed / 54 files / 0 skipped**; 25 test liên quan đạt ở task 4.
  Coverage statements 84.55%, branches 82.34%, functions 80.87%, lines 86.95%.

Kiểm UTF-8 tài liệu đạt **2 passed** (frontend-docs-utf8-2026-11-19.log).
Đã dừng stack E2E, xóa đúng container QA và file mật khẩu seed tạm.

Bằng chứng UTF-8 trong docs/evidence/final:

- frontend-search-wildcard-green-2026-11-19.log/JSON và ba JSON
  frontend-search-wildcard-result-r1/r2/r3-2026-11-19.json.
- frontend-search-limit-red-2026-11-19.log và bản green.
- frontend-empty-page-red-2026-11-19.log và bản green.
- frontend-status-empty-red-2026-11-19.log và bản green.
- frontend-final-*-2026-11-19.log và frontend-gates-2026-11-19.json
  ghi lệnh, exit code, head lúc chạy và hash mã nguồn cuối.

Lượt đỏ dùng -t để chọn riêng regression, các test khác không được chọn.
Suite tổng hợp cuối chạy đủ 319 test và 0 skipped.

### Việc chung còn chờ

Lúc kiểm cuối chưa có PR mới của B ngày 19/11. Khi B mở PR, review và
comment trong 18 giờ. Đây là việc chung còn chờ, 5 việc của A đã có kết quả
local. Các commit đang ở nhánh vantuong, chưa push hoặc mở PR trong bước này.
