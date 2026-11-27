# 2026-11-26 · Member A: chữ của từng ý trong tóm tắt, audio mất file khác audio hết hạn, E2E bấm dẫn chứng, API từ chối dẫn chứng (Đợt 16, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #77 (A) và #78 (B) đã vào `main` (`db8072b`, `3dd5ae0`). C gộp hai PR với `main` rồi chạy lại trước khi merge: backend trên PostgreSQL 16 551 passed, 0 xfailed; frontend 341 passed, 0 skipped; E2E `summary-edit.spec.ts` 1 passed trên API thật.
- **Review:** B review #77 sau 2,7 giờ, trong hạn. B ghi sai tên hai hằng (`ACTION_ITEM_DESC_MAX_LENGTH`, `ACTION_ITEM_ASSIGNEE_MAX_LENGTH`), còn tên trong code là `TASK_DESCRIPTION_MAX_LENGTH`, `TASK_ASSIGNEE_NAME_MAX_LENGTH`. Giá trị thì đúng. C để lại hai ghi chú P3 trên #77, không cần sửa hôm nay.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-26. Không phụ thuộc PR của B: số 1000 ở việc 1 đã chốt hôm nay, B làm phía API cùng số đó.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [x] Ô chữ của từng ý chính và quyết định không có giới hạn độ dài (FE-12)
- **Lỗi:** trong `RemoteSummary.tsx`, ô chữ của mỗi ý chính và quyết định không có `maxLength`, và `save()` chỉ kiểm chữ rỗng.
- Hôm nay B đặt giới hạn 1 đến 1000 ký tự phía API (`tasks/2026-11-26/member-b.md`, việc 1). C đã có test trên PostgreSQL cho thấy API hiện vẫn lưu ý dài 1001 ký tự.
- **Test đỏ trước:**
  - Dán 1001 ký tự vào một ý chính và một quyết định: request gửi đi chỉ có 1000.
  - Ý có đúng 1000 ký tự thì lưu được.
- **Sửa:**
  - Thêm hằng `SUMMARY_POINT_TEXT_MAX_LENGTH = 1000` vào `limits.ts`, có ghi chú dẫn tới schema đầu vào của B.
  - Kiểm thêm độ dài trong `save()`.
- **Message:** `fix(frontend): each summary key point and decision stops at 1000 characters, the limit the API accepts (FE-12)`
- **Commit:** `caae61a`

### 2. [x] Player báo "hết hạn" cả khi audio chỉ là mất file (FE-19)
- **Lỗi:** `RemoteAudioPlayer.tsx` (dòng 63) hiện "Audio đã hết hạn lưu trữ" mỗi khi `audio.available` là false.
- Hôm nay B sửa để `available` là false cả khi file đã mất mà hạn lưu chưa tới (`member-b.md`, việc 2). Trong trường hợp đó, chữ "hết hạn" là sai.
- Probe `Range: bytes=0-0` chỉ nhận 410. Khi `GET /audio` trả 404 `AUDIO_NOT_FOUND`, người dùng chỉ thấy lỗi phát chung chung.
- **Test đỏ trước (MSW):**
  - `available: false` và `retention_until` đã qua: vẫn báo "hết hạn" như cũ.
  - `available: false` và `retention_until` còn ở tương lai (hoặc `null`): báo không tìm thấy file audio, transcript vẫn đọc được.
  - Probe trả 404 `AUDIO_NOT_FOUND`: báo như trường hợp trên. Probe trả 410: báo hết hạn.
- **Message:** `fix(frontend): a meeting whose audio file is missing says so instead of saying the audio expired (FE-19)`
- **Commit:** `f432123`

### 3. [x] E2E trên API thật: bấm dẫn chứng của một ý chính thì audio tua tới segment đó (FE-18, FE-17)
- Chưa có E2E nào bấm vào `EvidenceLinks` trên API thật.
- **Kịch bản:**
  - Dùng cuộc họp `ready` có tóm tắt mà ý chính có `evidence_segment_ids`.
  - Bấm nút "Nghe bằng chứng từ …".
  - Kiểm: `currentTime` của audio nằm trong khoảng `start_sec` đến `end_sec` của segment đó (lấy từ `GET /meetings/{id}/transcript`).
- Chạy 3 lượt, `--retries=0`, **không** đặt `E2E_MANUAL_WORKER` (biến này tắt worker).
- Log UTF-8 ở `docs/evidence/final/frontend-evidence-seek-e2e-2026-11-26.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API seeks the audio to the segment a summary point cites (FE-18, FE-17)`
- **Commit:** `3bf1743`

### 4. [x] API từ chối dẫn chứng của tóm tắt (422 `EVIDENCE_SEGMENT_NOT_IN_MEETING`) thì editor làm gì? (FE-12, FE-18)
- Từ #78, `PUT /summary` trả 422 `EVIDENCE_SEGMENT_NOT_IN_MEETING` khi dẫn chứng không thuộc cuộc họp. `errors.ts` đã có câu tiếng Việt cho mã này.
- **Test (MSW trả 422 với mã đó):**
  - Câu báo lỗi hiện gần nút lưu.
  - Bản nháp còn nguyên: tổng quan, ý đã thêm, quyết định đã xóa.
  - Nút lưu bấm lại được và gửi request mới.
- Đỏ trước nếu sai, rồi sửa. Nếu đã đúng thì ghi "không có lỗi", giữ test, và đổi tiền tố thành `test(frontend)`.
- **Message:** `test(frontend): a summary the API rejects for its evidence keeps the draft and says why (FE-12, FE-18)`
- **Commit:** `ff5b033`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-26 member A results (G0)`
- **Commit:** `commit này`

## Việc chung (không tính commit)

- Review PR ngày 11-26 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub. #78 hôm qua chưa có review của A.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.


## Kết quả local — 26/11/2026

Đã cập nhật vantuong theo origin/main 9e501cb trước khi code. Hoàn thành phần triển khai 5 việc theo đúng thứ tự/5 commit; tick ở trên là kết quả local. Chưa push/mở PR/CI GitHub hoặc merge đợt này.

- Việc 1: maxLength=1000 và kiểm độ dài sau trim khi lưu cho cả ý chính/quyết định. Không cắt/chặn đọc ý dài đã lưu. Trước sửa 4 failed/5 passed; sau sửa nhóm summary/BusyEdits 20 passed/3 file, 0 skipped. API chặn đầu vào vẫn thuộc B.
- Việc 2: phân biệt mất file và hết hạn theo retention lúc mở/probe 404/410. Nhận cả NOT_FOUND hiện tại và AUDIO_NOT_FOUND của task; không đổi contract. Trước sửa 4 failed/4 passed; sau sửa 8 passed/1 file, 0 skipped, đồng hồ cố định.
- Việc 3: E2E API thật/PostgreSQL 16 đạt 3/3 lượt, retries=0, 0 failed/0 skipped/0 pageerror. WAV tổng hợp 60 giây; bấm EvidenceLinks đưa audio từ 0 tới 6, thuộc segment 6–11,2 lấy từ API, không tự phát. Không intercept API, không đặt E2E_MANUAL_WORKER; worker fake chạy. finally dọn meeting/user; container QA đã xóa. Helper lỗi console cp1252 sau lượt 1 đã đạt và đã cleanup; đổi stdout UTF-8, tiếp tục lượt 2,3 mà không sửa source/chạy lại lượt 1, ghi rõ trong JSON.
- Việc 4: **không có lỗi**, test MSW đạt ngay. 422 dẫn chứng hiện lời nhắc cạnh Lưu, giữ tổng quan/ý mới/quyết định đã xóa, cho gửi lại cùng content/version. Không sửa production, chuyển tiền tố commit sang test(frontend).
- Việc 5: lint sạch, format và TypeScript đạt, build đạt. npm test -- --coverage: **352 passed/58 file, 0 failed, 0 skipped**. Coverage lines **88.31%**, branches **83.34%**; giữ floors 84.53%/79.11%. Sinh schema API rồi git diff không drift. Server QA cổng 14173/18000 và container riêng đã dừng/xóa.

Docs: FE-12, FE-17, FE-18, FE-19 và frontend/README.md. Bằng chứng UTF-8 trong docs/evidence/final: frontend-summary-point-text-{red,green}, frontend-audio-missing-{red,green}, frontend-summary-evidence-rejected, frontend-evidence-seek-e2e và result r1/r2/r3, frontend-gates (đều hậu tố 2026-11-26).

### Việc chung còn chờ

- Kiểm GitHub lúc 12:44 ngày 26/11 (giờ Việt Nam): không có PR mở. Cần review/comment PR ngày 11-26 của B trong 18 giờ sau khi mở. #78 hôm qua đã merge mà chưa có review của A; không coi là đã hoàn thành review.
- Đã đọc review #77 của B/C. Tên đúng là TASK_DESCRIPTION_MAX_LENGTH/TASK_ASSIGNEE_NAME_MAX_LENGTH; hai P3 của C không bắt buộc sửa hôm nay. Chưa đăng trả lời trên #77 trong lượt local, còn bước phản hồi khi xuất bản công việc. Không thêm refactor ngoài 5 việc.

Bản nháp phản hồi #77 đã soạn tại docs/frontend/reviews/PR-77-response-2026-11-26.md; chưa đăng, không đánh dấu hoàn tất phần trả lời review.
