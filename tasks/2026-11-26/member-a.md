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

### 1. [ ] Ô chữ của từng ý chính và quyết định không có giới hạn độ dài (FE-12)
- **Lỗi:** trong `RemoteSummary.tsx`, ô chữ của mỗi ý chính và quyết định không có `maxLength`, và `save()` chỉ kiểm chữ rỗng.
- Hôm nay B đặt giới hạn 1 đến 1000 ký tự phía API (`tasks/2026-11-26/member-b.md`, việc 1). C đã có test trên PostgreSQL cho thấy API hiện vẫn lưu ý dài 1001 ký tự.
- **Test đỏ trước:**
  - Dán 1001 ký tự vào một ý chính và một quyết định: request gửi đi chỉ có 1000.
  - Ý có đúng 1000 ký tự thì lưu được.
- **Sửa:**
  - Thêm hằng `SUMMARY_POINT_TEXT_MAX_LENGTH = 1000` vào `limits.ts`, có ghi chú dẫn tới schema đầu vào của B.
  - Kiểm thêm độ dài trong `save()`.
- **Message:** `fix(frontend): each summary key point and decision stops at 1000 characters, the limit the API accepts (FE-12)`
- **Commit:** _chưa_

### 2. [ ] Player báo "hết hạn" cả khi audio chỉ là mất file (FE-19)
- **Lỗi:** `RemoteAudioPlayer.tsx` (dòng 63) hiện "Audio đã hết hạn lưu trữ" mỗi khi `audio.available` là false.
- Hôm nay B sửa để `available` là false cả khi file đã mất mà hạn lưu chưa tới (`member-b.md`, việc 2). Trong trường hợp đó, chữ "hết hạn" là sai.
- Probe `Range: bytes=0-0` chỉ nhận 410. Khi `GET /audio` trả 404 `AUDIO_NOT_FOUND`, người dùng chỉ thấy lỗi phát chung chung.
- **Test đỏ trước (MSW):**
  - `available: false` và `retention_until` đã qua: vẫn báo "hết hạn" như cũ.
  - `available: false` và `retention_until` còn ở tương lai (hoặc `null`): báo không tìm thấy file audio, transcript vẫn đọc được.
  - Probe trả 404 `AUDIO_NOT_FOUND`: báo như trường hợp trên. Probe trả 410: báo hết hạn.
- **Message:** `fix(frontend): a meeting whose audio file is missing says so instead of saying the audio expired (FE-19)`
- **Commit:** _chưa_

### 3. [ ] E2E trên API thật: bấm dẫn chứng của một ý chính thì audio tua tới segment đó (FE-18, FE-17)
- Chưa có E2E nào bấm vào `EvidenceLinks` trên API thật.
- **Kịch bản:**
  - Dùng cuộc họp `ready` có tóm tắt mà ý chính có `evidence_segment_ids`.
  - Bấm nút "Nghe bằng chứng từ …".
  - Kiểm: `currentTime` của audio nằm trong khoảng `start_sec` đến `end_sec` của segment đó (lấy từ `GET /meetings/{id}/transcript`).
- Chạy 3 lượt, `--retries=0`, **không** đặt `E2E_MANUAL_WORKER` (biến này tắt worker).
- Log UTF-8 ở `docs/evidence/final/frontend-evidence-seek-e2e-2026-11-26.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API seeks the audio to the segment a summary point cites (FE-18, FE-17)`
- **Commit:** _chưa_

### 4. [ ] API từ chối dẫn chứng của tóm tắt (422 `EVIDENCE_SEGMENT_NOT_IN_MEETING`) thì editor làm gì? (FE-12, FE-18)
- Từ #78, `PUT /summary` trả 422 `EVIDENCE_SEGMENT_NOT_IN_MEETING` khi dẫn chứng không thuộc cuộc họp. `errors.ts` đã có câu tiếng Việt cho mã này.
- **Test (MSW trả 422 với mã đó):**
  - Câu báo lỗi hiện gần nút lưu.
  - Bản nháp còn nguyên: tổng quan, ý đã thêm, quyết định đã xóa.
  - Nút lưu bấm lại được và gửi request mới.
- Đỏ trước nếu sai, rồi sửa. Nếu đã đúng thì ghi "không có lỗi", giữ test, và đổi tiền tố thành `test(frontend)`.
- **Message:** `fix(frontend): a summary the API rejects for its evidence keeps the draft and says why (FE-12, FE-18)`
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-26 member A results (G0)`
- **Commit:** _chưa_

## Việc chung (không tính commit)

- Review PR ngày 11-26 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub. #78 hôm qua chưa có review của A.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.
