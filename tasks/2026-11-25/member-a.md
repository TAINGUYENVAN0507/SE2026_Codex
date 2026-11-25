# 2026-11-25 · Member A: giới hạn của tóm tắt và công việc trên cuộc họp thật, E2E sửa tóm tắt, ngày họp bị API từ chối (Đợt 15, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #74 (A) và #75 (B) đã vào `main` (`46feb59`, `70b527a`). C review cả hai, gộp hai PR với `main` rồi chạy backend trên PostgreSQL 16 trước khi merge.
- **Review:** B review #74 sau 12,4 giờ, trong hạn. Ghi chú "ô tên cuộc họp chưa có `maxLength`" của B không đúng: dòng 272 có `maxLength={200}`. A review #75 sau 0,5 giờ, và finding P2 về thứ tự job mới nhất là đúng: C tái hiện được, giao B việc 1 hôm nay.
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR trong ngày 11-25. Không phụ thuộc PR của B.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

Log ghi **UTF-8**.

## Việc

### 1. [ ] Nút "Thêm ý chính" và "Thêm quyết định" không dừng ở 50 mục (FE-12)
- **Lỗi:** `frontend/src/features/meetings/RemoteSummary.tsx` (nút "Thêm …" cuối mỗi mục) thêm mục mới mà không kiểm số lượng. `SummaryContentOut.key_points` và `decisions` có `max_length=50` (`backend/app/schemas/summary.py`), nên lưu với 51 mục thì API trả 422.
- **Test đỏ trước:** có 50 ý chính thì nút "Thêm ý chính" bị tắt và có dòng giải thích. Quyết định cũng vậy. Có 49 mục thì vẫn thêm được. Đặt hằng số trong `limits.ts`.
- **Message:** `fix(frontend): the summary editor stops adding key points and decisions at 50, the limit the API accepts (FE-12)`
- **Commit:** _chưa_

### 2. [ ] Ô của công việc và tổng quan trên cuộc họp thật không có giới hạn độ dài (FE-12, FE-13)
- **Lỗi:** bản demo (`NotesPanel.tsx`) đã có `maxLength`. Bản dùng API thật thì không:
  - `RemoteTasks.tsx`: ô nội dung (`ActionItemCreate.description`, tối đa 1000) và ô người phụ trách (`assignee_name`, tối đa 100) không có `maxLength`.
  - `RemoteSummary.tsx`: ô "Chỉnh sửa tổng quan" (tối đa 5000) chỉ kiểm khi bấm lưu, không chặn lúc gõ.
- **Test đỏ trước:** dán quá giới hạn, request gửi đi đúng giới hạn và không có 422. Dùng hằng số chung trong `limits.ts`, có ghi chú dẫn tới schema backend.
- **Message:** `fix(frontend): task and overview fields on real meetings stop at the limits the API accepts (FE-12, FE-13)`
- **Commit:** _chưa_

### 3. [ ] E2E trên API thật: sửa tóm tắt còn sau khi tải lại và có trong lịch sử (FE-12, FE-14, FE-17)
- `frontend/e2e/flows/edit.spec.ts` mới kiểm transcript, người nói và công việc, chưa kiểm tóm tắt. Kịch bản:
  - Dùng cuộc họp `ready` có tóm tắt.
  - Sửa tổng quan, thêm 1 ý chính, xóa 1 quyết định, rồi lưu.
  - Tải lại trang: nội dung mới còn nguyên.
  - Tab "Lịch sử" có đúng 1 event của tóm tắt.
- Chạy 3 lượt, `--retries=0`. Log UTF-8 `docs/evidence/final/frontend-summary-edit-e2e-2026-11-25.log`. Dọn dữ liệu trong `finally`.
- **Message:** `test(frontend): e2e on the real API keeps an edited summary after reload and logs it in history (FE-12, FE-14, FE-17)`
- **Commit:** _chưa_

### 4. [ ] Ngày họp bị API từ chối (422) thì form tạo cuộc họp báo gì? (FE-05)
- Từ #75, `POST /meetings` trả 422 khi `meeting_date` không phải ngày `YYYY-MM-DD` hợp lệ. Ô `type="date"` (`NewMeetingPage.tsx`) thường gửi đúng định dạng, nhưng vẫn cần kiểm khi API từ chối.
- **Test** (MSW trả 422 cho `meeting_date`):
  - Form báo lỗi bằng tiếng Việt, gần ô ngày.
  - Giữ file đã chọn và tiêu đề đã gõ, không tạo cuộc họp.
  - Bấm gửi lại sau khi sửa ngày thì dùng `Idempotency-Key` mới.
- Đỏ trước nếu sai, rồi sửa; nếu đúng thì ghi "không có lỗi" và giữ test, đổi tiền tố thành `test(frontend)`.
- **Message:** `fix(frontend): a meeting date the API rejects is shown next to the date field and keeps the chosen file (FE-05)`
- **Commit:** _chưa_

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- Chạy `npm run lint`, `npm test`, `npm run build`. Ghi số test và số skipped.
- **Message:** `docs(tasks): record 2026-11-25 member A results (G0)`
- **Commit:** _chưa_

## Việc chung (không tính commit)

- Review PR ngày 11-25 của B **trong 18 giờ** kể từ lúc B mở, comment trên GitHub.
- Trả lời từng điểm review (nếu có) trên PR, ghi commit sửa.
