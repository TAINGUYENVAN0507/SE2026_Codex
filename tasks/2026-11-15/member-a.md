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

### 1. [x] Giao diện và MSW theo API sau #56 (FE-20, BE-05)
- Từ #56, `GET /meetings/{id}/summary` trả `failed` khi meeting `partial` và chưa có row Summary. Comment ở `frontend/src/features/meetings/RemoteSummary.tsx:111` ("API hiện có thể trả pending khi meeting partial") đã cũ: sửa thành "API từ #56 trả failed; nhánh pending + summaryFailed giữ cho dữ liệu cũ".
- `frontend/src/mocks/handlers.ts`: meeting `partial` trả summary `status: "failed"`, như API thật.
- Test: API trả `failed` → hiện "Tạo lại tóm tắt", không hiện skeleton "Đang tạo tóm tắt…". Giữ `PartialSummaryRetry.test.tsx` (ca API cũ trả pending).
- **Kiểm:** `npm run test -- RemoteSummary PartialSummaryRetry`, `npm run lint`, `npm run typecheck`.
- **Message:** `test(frontend): failed summary from the API after #56 (FE-20, BE-05)`

### 2. [x] Poll tóm tắt dừng khi API báo `failed` (FE-20)
- `RemoteSummary.tsx:37` poll mỗi 5 s khi `status === 'pending'`. Trước #56, meeting `partial` trả `pending` nên trang poll mãi.
- Test bằng fake timer: API trả `failed` → sau 15 s vẫn chỉ 1 lần GET summary; API trả `pending` → có GET lần 2. Mutant tạm (không commit): `refetchInterval: () => 5000` (luôn poll) thì ca `failed` phải đỏ; ghi kết quả mutant vào message commit.
- **Kiểm:** `npm run test -- RemoteSummary`.
- **Message:** `test(frontend): summary polling stops once the API reports failed (FE-20)`

### 3. [x] E2E kiểm API thật trả `failed` cho meeting `partial` (FE-20, BE-05)
- `frontend/e2e/evidence/progress.spec.ts` (scenario `summary_fail`) hiện chỉ đợi job failed rồi tìm nút. Thêm assert trên response thật: `GET /meetings/{id}/summary` trả `status: "failed"` và meeting `status: "partial"`. Đây là lần đầu lỗi A báo ở #53 được kiểm đầu-cuối trên API thật.
- Chạy `FAKE_SCENARIO=summary_fail`, `retries=0`, một lượt trên `main` sau #56. Đỏ thì giữ log đỏ.
- Log ghi **UTF-8** vào `docs/evidence/final/frontend-summary-fail-2026-11-15.log`. PowerShell `>` ghi UTF-16 (GitHub hiện là file nhị phân): dùng `... 2>&1 | Out-File -Encoding utf8 <file>`. Từ hôm nay có test chặn file bằng chứng không phải UTF-8 (C, việc 1).
- **Message:** `test(frontend): e2e checks the real API reports failed for a partial meeting (FE-20, BE-05)`

### 4. [x] Ảnh màn tóm tắt lỗi cho kịch bản demo (FE-20, VT-018)
- `docs/demo/ux-checklist.md` bước 02:00–02:30 ghi "**Chưa có ảnh riêng màn lỗi được duyệt**". Chụp `docs/evidence/vt-018/ui/05-summary-failed.png` trong cùng lượt E2E ở việc 3: transcript đọc được, thông báo "Tạo tóm tắt thất bại.", nút "Tạo lại tóm tắt".
- Thêm ảnh vào `manifest.json` (nguồn, commit, sha256) và `capture.json`; sửa bước 02:00–02:30 trỏ tới ảnh mới, ghi ngày 15/11. Bốn ảnh cũ giữ nguyên ngày 12/11.
- **Message:** `test(frontend): capture the failed-summary screen for the demo (FE-20, VT-018)`

### 5. [x] Tick, hash (G0)
- Ghi hash từng commit; hash của chính commit này ghi "commit này".
- `tasks/2026-11-13/member-a.md` dòng cuối ghi "chưa push, mở PR, xác nhận CI hoặc merge": sửa thành "#57 merge `115c905` ngày 11-15".
- **Message:** `docs(tasks): record 2026-11-15 member A results (G0)`

## Việc chung (không tính commit)

- Comment review lên PR ngày 11-15 của B trong 18 giờ kể từ lúc B mở PR (đọc diff, chạy test liên quan, ghi kết quả). Nhóm trưởng vẫn merge khi CI xanh, không chờ review. Lý do: `docs/evidence/pr-response-times.md` hiện ghi 18/23 PR merge khi chưa có phản hồi của người khác (RE-018 20 giờ, AD-018 18 giờ đang ◐).


## Kết quả thực hiện local - 15/11/2026

| Việc | Commit | Kết quả |
| --- | --- | --- |
| 1 - API failed và mock/UI | `bcdb181` | 9 test summary + fallback pending đạt, lint/typecheck đạt |
| 2 - polling và mutant | `88789ca` | Failed chỉ 1 GET/15 giây, pending gọi lần 2; mutant 1 fail/1 pass (4 GET thay vì 1), khôi phục 10 test xanh |
| 3 - E2E API thật | `dd374b6` | Source cuối 1 E2E đạt, retries=0; meeting partial, API/UI summary failed, transcript 6 segment đọc được |
| 4 - ảnh demo | `53e9755` | 05-summary-failed.png ngày 15/11, manifest/capture nguồn/hash; bốn ảnh 12/11 nguyên byte/ngày |
| 5 - tick/hash | commit này | Ghi kết quả, giới hạn và trạng thái chờ review; tổng 5 commit được giao |

### Kiểm tra cuối

- Đã cập nhật `vantuong` theo main `f8d22fd` bằng fast-forward, không conflict.
- Frontend: lint, format:check, typecheck, production build đạt. Full coverage:
  **305 test / 52 file**, 0 skip, lines **86.78%**, branches **81.63%**, giữ ngưỡng
  84.53/79.11. [JSON gate](../../docs/evidence/final/frontend-gates-2026-11-15.json),
  [log unit](../../docs/evidence/final/frontend-unit-2026-11-15.log).
- Hai test UTF-8 docs/tasks đạt. Log mới UTF-8, không có BOM UTF-16/NUL.
- E2E cuối dùng API/worker/PostgreSQL 16 thật, pipeline fake summary_fail,
  không MSW/intercept. Một ca duy nhất, không lấy lượt chạy lặp làm ca mới.
  [Log cuối](../../docs/evidence/final/frontend-summary-fail-2026-11-15.log),
  [JSON các lượt và source/hash](../../docs/evidence/final/frontend-summary-fail-2026-11-15.json).
- Giữ log đỏ của lượt chuẩn bị bị 401: script local sinh mật khẩu mới trong khi
  seed DB cũ giữ mật khẩu trước. Đã dùng DB E2E mới và source cuối đạt. Đây là lỗi
  chuẩn bị, không phải regression summary hoặc lý do sửa code auth. Lượt đầu
  source cũ cũng pass; không coi ba lượt là bằng chứng hết flaky.
- Mutation luôn poll chỉ ở working tree tạm, phục hồi nguyên byte trong finally;
  không có mutation trong commit. Test failed bắt 4 request thay vì 1.
- Ảnh mới đã xem local. Root date/source bộ ảnh cũ vẫn 12/11;
  `additional_captures` và `capture.json.summary_failed` mô tả riêng ngày 15/11.
- PostgreSQL QA `se-day9-e2e-db` đúng nhãn 20261115-member-a đã dọn. Cổng
  14173/18000/55455 không còn listener của QA, không dừng dịch vụ người dùng.
- README chung và bản Lab03 không đổi. Chưa push, mở PR, xác nhận CI hoặc merge
  cho đợt 15/11; cần người dùng cho phép push trước khi công bố.

### Việc chung còn chờ

Kiểm tra GitHub lúc kết thúc phần triển khai: chưa có PR đang mở, nên chưa có
PR ngày 15/11 của B để đọc diff/chạy test/đăng nhận xét. **Chưa hoàn thành review**,
không tick thay. Khi B mở PR, cần review trong 18 giờ từ created_at, ghi link,
commit được review và kết quả kiểm thật. Không tự merge.
