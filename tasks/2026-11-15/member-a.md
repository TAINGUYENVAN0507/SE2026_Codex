# 2026-11-15 · Member A: giao diện theo API sau #56, ảnh màn tóm tắt lỗi (Đợt 9, sau hạn nộp)

- **Người làm:** A (`@mactuongmvt`), nhánh `vantuong`.
- **Số commit:** 5.
- **Điều kiện bắt đầu:** #56 (B) và #57 (A) đã vào `main` (C review diff, chạy backend trên bản gộp 444 passed; #56 CI xanh 15/15; merge `1e71c89`, `115c905`).
- **Phạm vi:** sau hạn nộp 11-14. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.
- **Hạn:** mở PR khi push xong, trong ngày 11-15.

## Bước 0
```bash
git checkout vantuong && git fetch origin && git merge origin/main
```

## Việc

### 1. [ ] Giao diện và MSW theo API sau #56 (FE-20, BE-05)
- Từ #56, `GET /meetings/{id}/summary` trả `failed` khi meeting `partial` và chưa có row Summary. Comment ở `frontend/src/features/meetings/RemoteSummary.tsx:111` ("API hiện có thể trả pending khi meeting partial") đã cũ: sửa thành "API từ #56 trả failed; nhánh pending + summaryFailed giữ cho dữ liệu cũ".
- `frontend/src/mocks/handlers.ts`: meeting `partial` trả summary `status: "failed"`, như API thật.
- Test: API trả `failed` → hiện "Tạo lại tóm tắt", không hiện skeleton "Đang tạo tóm tắt…". Giữ `PartialSummaryRetry.test.tsx` (ca API cũ trả pending).
- **Kiểm:** `npm run test -- RemoteSummary PartialSummaryRetry`, `npm run lint`, `npm run typecheck`.
- **Message:** `test(frontend): failed summary from the API after #56 (FE-20, BE-05)`

### 2. [ ] Poll tóm tắt dừng khi API báo `failed` (FE-20)
- `RemoteSummary.tsx:37` poll mỗi 5 s khi `status === 'pending'`. Trước #56, meeting `partial` trả `pending` nên trang poll mãi.
- Test bằng fake timer: API trả `failed` → sau 15 s vẫn chỉ 1 lần GET summary; API trả `pending` → có GET lần 2. Mutant tạm (không commit): `refetchInterval: () => 5000` (luôn poll) thì ca `failed` phải đỏ; ghi kết quả mutant vào message commit.
- **Kiểm:** `npm run test -- RemoteSummary`.
- **Message:** `test(frontend): summary polling stops once the API reports failed (FE-20)`

### 3. [ ] E2E kiểm API thật trả `failed` cho meeting `partial` (FE-20, BE-05)
- `frontend/e2e/evidence/progress.spec.ts` (scenario `summary_fail`) hiện chỉ đợi job failed rồi tìm nút. Thêm assert trên response thật: `GET /meetings/{id}/summary` trả `status: "failed"` và meeting `status: "partial"`. Đây là lần đầu lỗi A báo ở #53 được kiểm đầu-cuối trên API thật.
- Chạy `FAKE_SCENARIO=summary_fail`, `retries=0`, một lượt trên `main` sau #56. Đỏ thì giữ log đỏ.
- Log ghi **UTF-8** vào `docs/evidence/final/frontend-summary-fail-2026-11-15.log`. PowerShell `>` ghi UTF-16 (GitHub hiện là file nhị phân): dùng `... 2>&1 | Out-File -Encoding utf8 <file>`. Từ hôm nay có test chặn file bằng chứng không phải UTF-8 (C, việc 1).
- **Message:** `test(frontend): e2e checks the real API reports failed for a partial meeting (FE-20, BE-05)`

### 4. [ ] Ảnh màn tóm tắt lỗi cho kịch bản demo (FE-20, VT-018)
- `docs/demo/ux-checklist.md` bước 02:00–02:30 ghi "**Chưa có ảnh riêng màn lỗi được duyệt**". Chụp `docs/evidence/vt-018/ui/05-summary-failed.png` trong cùng lượt E2E ở việc 3: transcript đọc được, thông báo "Tạo tóm tắt thất bại.", nút "Tạo lại tóm tắt".
- Thêm ảnh vào `manifest.json` (nguồn, commit, sha256) và `capture.json`; sửa bước 02:00–02:30 trỏ tới ảnh mới, ghi ngày 15/11. Bốn ảnh cũ giữ nguyên ngày 12/11.
- **Message:** `test(frontend): capture the failed-summary screen for the demo (FE-20, VT-018)`

### 5. [ ] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- `tasks/2026-11-13/member-a.md` dòng cuối ghi "chưa push, mở PR, xác nhận CI hoặc merge": sửa thành "#57 merge `115c905` ngày 11-15".
- **Message:** `docs(tasks): record 2026-11-15 member A results (G0)`

## Việc chung (không tính commit)

- Comment review lên PR ngày 11-15 của B trong 18 giờ kể từ lúc B mở PR (đọc diff, chạy test liên quan, ghi kết quả). Nhóm trưởng vẫn merge khi CI xanh, không chờ review. Lý do: `docs/evidence/pr-response-times.md` hiện ghi 18/23 PR merge khi chưa có phản hồi của người khác (RE-018 20 giờ, AD-018 18 giờ đang ◐).
