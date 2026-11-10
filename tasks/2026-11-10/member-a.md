# 2026-11-10 · Member A: giao diện chịu được quá tải, thời gian job, E2E qua container web (Đợt 5)

- **Người làm:** A (`@vantuong`), nhánh `vantuong`.
- **Số commit:** 10, **cộng việc review**.
- **Điều kiện bắt đầu:** #44 và #45 đã vào `main` (2026-11-10).
- **Hạn:** mở PR trước tối 11-11. Ngày 11-12 đóng băng code (chỉ sửa lỗi), xem [`tasks/ROADMAP.md`](../ROADMAP.md), mục Lịch tới hạn nộp.
- **Mục tiêu:** từ #43, API trả `503 SERVICE_UNAVAILABLE` kèm `Retry-After: 2` khi quá tải (`backend/app/core/admission.py`). Giao diện chưa biết xử lý trường hợp này. Thêm vào đó: giao diện hiện thời gian thật của job (VT-018), và E2E chạy qua đúng đường người dùng đi (nginx → API).

Kiểm tra trong `frontend/`: `npm run lint && npm test && npm run build`. E2E: `npm run e2e` như các đợt trước.

## Review (không bắt buộc, không tính commit)
Từ 2026-11-10, nhóm trưởng quyết định PR không cần chờ review của thành viên khác. Nhóm trưởng tự review diff, chờ CI xanh rồi merge. Nhận xét của bạn vẫn có ích nhưng không chặn merge.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## 10 commit

### 1. [x] Upload gặp 503: thông báo và tự thử lại với cùng `Idempotency-Key` (AD-018, VT-018)

**Kết quả 10/11:** MSW đỏ trước, xanh sau: 2 lần 503 rồi 201 = 3 request cùng key/1 meeting; 4 lần 503 hiện thử lại; hủy khi chờ không chuyển trang. Timer kiểm mặc định 2 giây và abort.

**Commit:** `132f43d76b806cc8c487e8ed832d98e186241226`.

- Khi `POST /meetings` trả 503 `SERVICE_UNAVAILABLE`, hiện thông báo tiếng Việt "máy chủ đang bận", đợi theo `Retry-After` (mặc định 2 s nếu thiếu), thử lại tối đa 3 lần với **cùng** `Idempotency-Key`. Hết lượt thì cho người dùng bấm thử lại, vẫn giữ key đó.
- Test MSW **đỏ trước**: 503 hai lần rồi 201 thì phải có đúng 1 meeting và 3 request cùng key; 503 bốn lần thì hiện nút thử lại.
- **Message:** `fix(frontend): upload waits and retries with the same key when the API is busy (AD-018)`

### 2. [x] Poll tiến độ lùi lại khi 503 hoặc lỗi mạng (VT-018, FE-20)

**Kết quả 10/11:** Fake timer 30 giây kiểm 5 request khi lỗi, không chồng request, 200 về 2 giây, giữ progress. Có regression dừng với 404, không hứa tự poll lại khi đã dừng.

**Commit:** `b385f891e65a671ada275012b1900189259ecc67`.

- Poll `GET /jobs/{id}` hiện chạy mỗi 2 s. Khi gặp 503 hoặc lỗi mạng thì giãn khoảng poll theo `Retry-After` hoặc tăng dần (tối đa 10 s), không chồng request. Có kết quả 200 thì về lại 2 s. Thanh tiến độ không tụt về 0 khi lỗi.
- Test dùng fake timer: đếm số request trong 30 s khi API lỗi liên tục.
- **Message:** `fix(frontend): progress polling backs off on busy or failed responses (VT-018)`

### 3. [x] Gặp 503 khi đang sửa thì không mất nội dung đã gõ (AD-018, FE-16)

**Kết quả 10/11:** 5 test MSW kiểm transcript, tên speaker, tóm tắt, retry job, xóa; giữ draft và retry thủ công. Transcript/speaker đã có test đỏ trước sửa. Không tự gửi lại thao tác xóa.

**Commit:** `13cbe79e383150067dc5968062095836475e7f4a`.

- Các thao tác ghi khác: sửa đoạn transcript, đổi tên speaker, sửa tóm tắt, chạy lại job, xóa. Khi API trả 503, giữ nguyên nội dung người dùng đã gõ, hiện "máy chủ đang bận" và nút thử lại. Không tự gửi lại thao tác xóa.
- (`src/api/errorCoverage.test.ts` đã kiểm mọi mã lỗi có thông báo; việc này kiểm **hành vi** của từng màn hình khi gặp 503.)
- Test MSW **đỏ trước** cho ít nhất sửa đoạn transcript và đổi tên speaker.
- **Message:** `fix(frontend): edits survive a busy API and can be retried (AD-018)`

### 4. [x] Hiện thời gian chờ trong hàng đợi, giờ bắt đầu và giờ xong (VT-018, FE-20)

**Kết quả 10/11:** Kiểm queued/running/completed và timestamp thiếu/invalid; local time, dừng timer khi terminal. Chi tiết dùng dòng gọn, mốc đầy đủ ở trang tiến độ riêng.

**Commit:** `fe8a8b13c98bdb2141c57816b6935de79c1bf21a`.

- `JobStatusCard` đã hiện "Đã chạy …" (`ElapsedTime`). Worker chạy mỗi lúc 1 job nên khi đông, job chờ lâu ở `queued`. Thêm "Đã chờ …" (từ `created_at` tới `started_at` hoặc tới hiện tại), cùng giờ bắt đầu và giờ xong theo giờ máy người dùng.
- Test cho 3 trạng thái: đang chờ, đang chạy, đã xong. Thiếu trường thì không hiện `NaN` hay `Invalid Date`.
- **Message:** `feat(frontend): show queue wait, start and finish time of a job (VT-018)`

### 5. [x] E2E qua container web trên Compose trong CI (BE-16, FE-19)

**Kết quả 10/11:** Đã chạy CI trên container web thật. [Run đỏ 42786190434](https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42786190434) fail đúng Playwright/nginx vì proxy `/api/` sang port 1; các bước cài đặt/Compose/seed/teardown đạt. [Run xanh 42786612344](https://github.com/TAINGUYENVAN0507/SE2026_Codex/actions/runs/42786612344) đạt 1 test sau khi khôi phục proxy; commit `189bb061ace8d46dd41d32a13f6a1463b5763db9` chứa link đỏ trong thân commit. Không đổi assertion hoặc skip test. Nhánh proof không merge. Infra healthcheck web/worker được nêu rõ để owner B xem; CI PR cuối kiểm riêng.

**Commit:** `a15a9f1f76be8213fc1a9915b4e69c37694f1b4d`.

- B đã có job `compose-smoke` (API). Thêm job (hoặc bước) chạy **một** spec Playwright vào `http://localhost:8080` qua nginx: đăng nhập → upload → chờ xong → export. Tạo user tổng hợp như `backend/scripts/smoke_compose.py`.
- **Xong khi:** CI chạy spec đó trên container web thật. Thử trên nhánh tạm: sửa sai `proxy_pass` trong `infra/nginx` làm job đỏ, dán link run đỏ vào thân commit, rồi trả lại.
- **Message:** `test(e2e): one Playwright flow through the web container on Compose (BE-16)`

### 6. [x] Chỉ dùng bàn phím đi hết luồng chính (FE-16)

**Kết quả 10/11:** Playwright dùng Tab/Enter/Space; kiểm focus từ login/upload tới mở lại/export. Sửa viền focus tìm kiếm và trả focus menu export. Đã đạt qua nginx và trong E2E clone sạch. Hộp chọn file OS được thay bằng filechooser.setFiles; chưa kiểm screen reader.

**Commit:** `b22b248d634589b79980e2bed7f5cdec17703f28`.

- Playwright: dùng Tab/Enter/Space để đăng nhập, upload, mở cuộc họp, export, không dùng chuột. Focus luôn nhìn thấy được. Gặp chỗ không đi được thì sửa.
- **Message:** `test(frontend): keyboard-only main flow (FE-16)`

### 7. [x] Coverage frontend có ngưỡng, ghi số thật (FE-16)

**Kết quả 10/11:** Vitest coverage V8 đo toàn bộ source TS/TSX, loại test/helper/mock/type sinh. Ban đầu 86.50% lines/80.75% branches; sau regression integration là **86.53%/81.11%**, ngưỡng **84.53%/79.11%**. Không thêm test chỉ để nâng số.

**Commit:** `46d96937becf8c3246e6aa916e8b9a51bac0b018`.

- Bật coverage (line và branch) trong Vitest, đặt ngưỡng bằng mức hiện tại trừ 2 điểm để không tụt. Ghi số đo được vào `frontend/README.md`. Không viết thêm test chỉ để kéo số.
- **Message:** `test(frontend): coverage thresholds at the measured level (FE-16)`

### 8. [x] Clone sạch: README frontend chạy đúng từng bước (G0)

**Kết quả 10/11:** Clone mới commit 8beb86e: npm ci/dev/build/test/E2E đạt trên Node v24.13.0/npm 11.6.2. 284 Vitest/46 file và 27 E2E qua 4 scenario. Đã sửa hướng dẫn MSW/API thật và PowerShell; xem báo cáo clone sạch.

**Commit:** `f213ba15cfa50590b9262db7ef8fea4cceffab09`.

- Clone repo vào thư mục mới, làm theo `frontend/README.md` và phần frontend trong `README.md`: `npm ci`, dev, build, test, E2E. Bước nào sai hoặc thiếu thì sửa tài liệu. Ghi phiên bản Node đã dùng.
- **Message:** `docs(frontend): README steps verified on a clean clone (G0)`

### 9. [x] Ảnh demo và kịch bản demo theo giao diện mới (FE-16)

**Kết quả 10/11:** 8 ảnh mới desktop/mobile và manifest SHA256, bản sao trong .preview-stitch ngoài Git. Kịch bản 5 phút cập nhật; mọi dữ liệu tổng hợp, 503 giả lập được ghi rõ, job hoàn thành dùng timestamp stack test.

**Commit:** `8ae9cdafac6923d87ff05e81508ae3ecf4827968`.

- Cập nhật `docs/demo/` cho thông báo bận, poll lùi lại, thời gian job. Chỉ dùng dữ liệu tổng hợp.
- **Message:** `docs(demo): screenshots and script for busy state and job times (FE-16)`

### 10. [x] Tick, hash (G0)
- Ghi hash từng commit vào file này. Việc chưa xong thì ghi "chuyển sang 11-11" và lý do, không tick.
- **Message:** `docs(tasks): record 2026-11-10 member A results (G0)`

## Tổng kiểm tra local — 10/11/2026

- Đã đồng bộ `origin/main` tại `40d2431` trước khi làm; PR #44/#45 đã merge.
- **10/10 mục đã hoàn thành; mục 5 có bằng chứng CI đỏ/xanh** như ghi ở trên.
  Có commit triển khai cho cả 9 mục kỹ thuật, không đồng nhất "đã code" với
  "đủ nghiệm thu CI". Review thành viên đã là tùy chọn từ hôm nay.
- Lint, format, TypeScript, **284 Vitest / 46 file**, coverage có ngưỡng và
  production build đạt. Type API sinh lại không tạo diff với contract.
- Clone sạch: **24 slow + 1 permanent + 1 transient_once + 1 summary_fail = 27 E2E**
  đạt, không skip. Một flow Compose qua nginx đã đạt riêng. Keyboard cũng chạy
  riêng qua nginx nhưng không đếm lại thành test chức năng mới.
- Bằng chứng: [clone sạch](../../docs/frontend/clean-clone-2026-11-10.md),
  [coverage](../../docs/frontend/coverage-2026-11-10.json),
  [ảnh/demo](../../docs/demo/ux-checklist.md),
  [ghi chú Compose](../../docs/frontend/FE-19.md).
- Còn cảnh báo `os.killpg` của worker native Windows khi hủy job. Đã ghi rõ
  giới hạn; không sửa pipeline của C, không dùng UI/API pass để kết luận
  subprocess cleanup đúng trên mọi nền tảng. Không chứng minh chất lượng AI
  hoặc khả năng chịu tải bằng pipeline fake. SH-01 là việc chung của nhóm.
- Đã dừng/dọn đúng stack test `se-web-e2e`, volume tổng hợp và container DB
  clone sạch; các cổng 8080/55450/15173/14173/18000 không còn listener của QA.
- Đã được người dùng cho làm nốt phần CI: push nhánh proof, giữ riêng mutation.
  Bản bàn giao từ vantuong mở PR sau khi ghi bằng chứng; không tự merge.
  Không đăng nhận xét mới lên PR người khác trong đợt này. Bản review #45 đã đăng ngày 09/11 được lưu lại ở G0, là snapshot
  `d9eba806`, không khẳng định các phát hiện đã được sửa sau merge.

**Sửa lỗi QA phát sinh:** `8beb86e148a15371bb978b2b6ba54b61985b59cb`: LF trên Windows, notice bận dễ đọc, thông báo khi poll đã dừng, cập nhật coverage thật. Đây là sửa lỗi ngoài danh sách task, không gán thành một task mới.

**Commit mục 10:** `9505efc7e9182ca58b41fd97c0200d344871093a`. Lần cập nhật sau chỉ ghi hash của commit tổng kết; không tính là task/feature hoặc bằng chứng kiểm thử mới.
