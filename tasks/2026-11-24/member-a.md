# 2026-11-24 · Member A: đổi tên cuộc họp không lưu lên API, giới hạn 5000 ký tự khi sửa transcript, dòng của trang cũ khi đang tải (Đợt 14, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #71 (C) và #72 (A) đã vào `main` (`6d5f94d`, `b35e06f`). C review #72 và chạy lại E2E trang rỗng trên API thật: 3/3 passed, `retries=0`.
- **Review:** #72 mở 11-24 02:50 UTC; B chưa review. B chưa mở PR cho việc ngày 11-23.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-24. Không phụ thuộc PR của B.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [x] Đổi tên cuộc họp thật chỉ đổi trên trình duyệt, không lưu lên API (FE-02, AD-018)
- **Lỗi:** `RemoteMeetingContent` (`frontend/src/pages/MeetingDetailPage.tsx`) truyền `onUpdate={(transform) => setMeeting(...)}`. Form "Đổi tên cuộc họp" chỉ đổi state cục bộ, và `frontend/src/api/client.ts` không có hàm nào gọi `PATCH /api/v1/meetings/{id}`. Người dùng thấy tên mới, tải lại trang thì tên cũ quay về. Đây là lỗi mất dữ liệu đã sửa (yêu cầu "sửa đổi được" của AD-018).
- **Test đỏ trước** (MSW):
  - Đổi tên thì phải có đúng 1 request `PATCH /meetings/{id}` với `{title, version}`.
  - Tên hiện ra là tên server trả về.
  - API trả 409 `VERSION_CONFLICT` hoặc 422: tên quay về tên cũ, hiện thông báo lỗi, ô vẫn mở để sửa lại.
  - Bản demo (không có API) giữ hành vi cũ.
- **Sửa:** thêm `patchMeeting` vào `client.ts` theo kiểu của `contracts/openapi.json`, và chỉ cuộc họp thật mới gọi nó.
- **Message:** `fix(frontend): renaming a meeting saves the title through PATCH /meetings/{id} and reverts on conflict (FE-02, AD-018)`
- **Commit:** `e60996fc0ab66d8827523c97b186af52740b0d44`

### 2. [x] E2E trên API thật: tên mới còn sau khi tải lại và tìm được trong danh sách (FE-17, FE-04)
- Tạo 1 cuộc họp qua API rồi đổi tên trên giao diện thành `Họp_đổi tên 100%`. Kiểm ba điều:
  1. Tải lại trang: tên vẫn là tên mới.
  2. `GET /meetings/{id}` trả tên mới và `version` tăng 1.
  3. Gõ `100%` vào ô tìm ở danh sách thì ra đúng cuộc họp đó.
- Chạy 3 lượt `--retries=0`. Log UTF-8 `docs/evidence/final/frontend-rename-e2e-2026-11-24.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API keeps a renamed meeting after reload and finds it by search (FE-17, FE-04)`
- **Commit:** `a23b749345896e343873d3ce5b3b63b73af794a5`

### 3. [x] Ô sửa transcript cho gõ quá 5000 ký tự (FE-10)
- **Lỗi:** `textarea` "Chỉnh sửa transcript" (`frontend/src/features/meetings/Transcript.tsx`, khối `segment-editor`) không có `maxLength`, trong khi `SegmentPatch.text` có `max_length=5000` (`backend/app/schemas/transcript.py`). Dán 5001 ký tự rồi lưu thì API trả 422.
- **Test đỏ trước:** dán 5001 ký tự, request gửi đi có `text` dài đúng 5000. Đặt hằng số dùng chung như `limits.ts` của #69.
- **Message:** `fix(frontend): the transcript editor stops at 5000 characters, the limit the API accepts (FE-10)`
- **Commit:** `b269c0f6e6c6713b38d42006bf3fbabe55ce897a`

### 4. [x] Dòng của trang cũ trông như trang mới trong lúc tải (FE-04, review #72)
- **Lỗi (review #72 của C):** từ `placeholderData`, khi bấm "Trang sau", danh sách vẫn hiện dòng của trang 1 dưới nhãn "Trang 2" mà không có dấu hiệu đang tải. Người dùng có thể bấm nhầm một cuộc họp của trang cũ.
- **Test đỏ trước** (MSW trễ trang 2): trong lúc `isPlaceholderData`, bảng có `aria-busy="true"` và các dòng cũ không bấm được (hoặc bị làm mờ và có nhãn "Đang tải trang 2…"). Khi trang 2 về thì bỏ hết các trạng thái đó. Thanh phân trang vẫn giữ nguyên như việc 3 ngày 11-23.
- **Message:** `fix(frontend): rows of the previous page are marked busy while the next page of meetings loads (FE-04)`
- **Commit:** `60cefea24367649f74b0a9964f40da12f2e347fd`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-24 member A results (G0)`
- **Commit:** `commit này`

## Việc chung (không tính commit)

- Review PR ngày 11-24 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.


## Kết quả thực hiện — 24/11/2026

- Bước 0: fetch và cập nhật vantuong bằng ff-only từ main `cc0aba8` trước code;
  #72 và #73 đã merge. Không sửa nhánh/main hoặc thư mục lab riêng.
- Việc 1: thêm patchMeeting theo OpenAPI. Đổi tên thật gửi một PATCH có title/version,
  dùng tên server trả về, cập nhật cache/version và invalidate danh sách. Trong lúc
  lưu khóa form/chặn submit lặp. 409/422 khôi phục tên cũ, giữ draft/form và báo lỗi.
  Demo vẫn lưu trong phiên; MSW giữ tên/version mới cho GET/tìm kiếm/export.
  Trước sửa ba regression đỏ, demo đạt; sau sửa bộ frontend 329 test/55 file đạt.
- Việc 2: E2E trên ba database PostgreSQL 16 mới, API thật: **3/3 đạt, retries=0**,
  0 pageerror. Đổi tên thành Họp_đổi tên 100%, reload giữ tên; GET version 1→2;
  tìm 100% đúng một kết quả/ID/footer. finally dọn meeting/user riêng.
- Việc 3: maxLength dùng TRANSCRIPT_TEXT_MAX_LENGTH=5000, validation trước lưu
  dùng cùng hằng số. Test paste 5001 đỏ trước sửa; xanh xác nhận request text đúng
  5000. Giữ validation rỗng/quá dài khi gán bằng chương trình. 16 test liên quan đạt.
- Việc 4: bảng aria-busy, nhãn đang tải trang, dòng cũ mờ và không còn link/tab stop;
  response thật về thì bỏ trạng thái chờ, phục hồi link mục mới. Thanh phân trang
  không mất. Regression trễ 500 ms đỏ trước sửa; 29 test danh sách/PageStates đạt,
  gồm race tìm kiếm và poll trang rỗng. Finding review #72 của C đã xử lý local.
- Smoke thêm trên API/PostgreSQL thật sau việc 4: trang 2 bị xóa hết tự về trang 1,
  bộ lọc Có lỗi báo đúng, 1/1 đạt, retries=0, không pageerror. Dọn 11 mục và user.
- Gate cuối: gen:api không drift; lint, format:check, typecheck, npm test,
  test:coverage, build đạt. **330 test/55 file, 0 failed, 0 skipped.**
  Coverage lines 87.83%, branches 82.76%, giữ floors 84.53%/79.11%.
- Docs cập nhật: FE-02, FE-17, FE-10, FE-04 và README frontend. README chung
  không đổi. Log UTF-8/test đỏ giữ trong docs/evidence/final/:
  frontend-rename-{red,green,e2e}-2026-11-24.*, ba kết quả E2E từng lượt,
  frontend-transcript-limit-{red,green}-2026-11-24.log,
  frontend-old-rows-{red,green}-2026-11-24.log,
  frontend-empty-page-smoke-2026-11-24.{log,json},
  frontend-gates-2026-11-24.{log,json}. Metadata có HEAD, lệnh và SHA-256 nguồn.
- Chỉ dùng dữ liệu/audio tổng hợp; E2E Chromium desktop, không chạy model AI.
  Container QA đã xóa; cổng API/preview/DB QA không còn lắng nghe.

### Chờ sau phần local

- Khoảng 19:29 (+07) ngày 24/11, GitHub không có PR mở; review PR ngày 24/11
  của B chưa làm vì chưa có PR. Khi B mở, review/comment trong 18 giờ.
- Đợt 14 chưa push/mở PR; chờ người dùng cho phép. CI GitHub chưa xác nhận
  cho source mới. Không tự merge. Tick phía trên là triển khai và kiểm thử local,
  chưa phải hoàn tất Definition of Done trên main.
