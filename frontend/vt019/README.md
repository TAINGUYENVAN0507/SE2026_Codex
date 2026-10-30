# VT-019 - Autosave transcript không mất draft mới

Nhánh cá nhân `vantuong-vt019-autosave`, baseline
`53f753b3afe6c1a2d54ff1e38a72dee30c6074d2`. Chưa merge, cần nhóm trưởng review.
Theo chỉ dẫn của sinh viên, mọi thao tác chỉ ở local: chưa push, chưa có PR hay
link branch công bố. Đề yêu cầu link GitHub nên thành phần này chưa hoàn tất.
Phạm vi: editor của một segment API. `sprint-42` không có version vẫn lưu tay.
Draft chỉ ở RAM; autosave PATCH ghi bản hiện tại, không tạo bảng draft riêng.
Hủy chỉ đóng editor, không undo phần đã lưu; refresh có thể mất phần chưa gửi.

## Chạy lại (trong frontend/)

Yêu cầu Node 24, npm; dependency được khóa bởi package-lock.json.

```bash
npm ci
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
node vt019/run.mjs green-full vitest run --coverage.enabled --coverage.provider=v8 --coverage.include=src/features/meetings/autosave.ts --coverage.include=src/features/meetings/AutosaveEditor.tsx --coverage.reporter=json-summary --coverage.reporter=text --coverage.reportsDirectory=vt019/evidence/coverage
npx playwright install chromium
node vt019/run.mjs e2e playwright test --config vt019/playwright.config.ts
node vt019/load.mts
```

PowerShell có thể dùng `npm.cmd`. Trên Windows clone với `core.autocrlf=false`
để tránh Prettier báo CRLF. Plugin `@vitest/coverage-v8@5.0.5` (MIT) chỉ dùng ở
dev, cùng version Vitest; không thêm runtime dependency.

E2E chạy SPA thật trong Chromium nhưng HTTP được intercept bằng fixture tổng hợp.
Không yêu cầu PostgreSQL, mật khẩu hay model AI; không gọi API production.

## Contract và test cases

| TC  | AC/risk              | Level            | Precondition/input            | Expected result                       | Priority |
| --- | -------------------- | ---------------- | ----------------------------- | ------------------------------------- | -------- |
| 01  | AC1 quên lưu         | Component        | Gõ text hợp lệ, 501 ms        | Một PATCH, giữ textbox                | P0       |
| 02  | AC2 response chậm    | Unit concurrency | A đang pending, edit B rồi C  | A không thay C; tiếp C/version2       | P0       |
| 03  | AC3 hai tab          | Unit concurrency | Hai editor cùng version1      | Một saved, một conflict; draft còn    | P0       |
| 04  | AC4 input sai        | Unit negative    | Rỗng, spaces, 5001 ký tự      | Không gọi adapter, status error       | P0       |
| 05  | AC4 boundary         | Unit             | 1 hoặc 5000 ký tự             | Lưu thành công                        | P1       |
| 06  | AC5 mạng lỗi         | Unit failure     | Reject rồi sửa draft/retry    | Giữ draft, retry bản mới nhất         | P0       |
| 07  | AC4 response version | Unit negative    | Version 0,1,NaN,1.5           | Không tiến version cục bộ             | P0       |
| 08  | AC5 đóng khi busy    | Unit concurrency | A pending, B queued, close    | A có thể commit; không gửi B          | P1       |
| 09  | AC1 no-op            | Unit             | Chỉ thêm khoảng trắng ngoài   | Không ghi dư                          | P2       |
| 10  | AC2 response sai     | Unit negative    | Response text không khớp      | Giữ draft, báo lỗi                    | P1       |
| 11  | AC1 timer            | Component        | Gõ B,499ms,gõ C,499+1ms       | Chỉ một PATCH C; StrictMode hoạt động | P0       |
| 12  | AC5 cleanup          | Component        | Unmount trước 500ms           | Không PATCH                           | P1       |
| 13  | AC2 UI race          | Component        | A pending, textbox C          | Textbox C kể cả sau A; tiếp PATCH C   | P0       |
| 14  | AC3 HTTP CAS         | Integration/MSW  | 2 client PATCH/version1       | Một 200, một 409; không retry mù      | P0       |
| 15  | AC5 HTTP500          | Integration/MSW  | 500, sau đó retry200          | Draft giữ nguyên, retry thành công    | P0       |
| 16  | AC1/2 browser        | Browser E2E mock | Hold response A, gõ C, reload | API fixture và giao diện giữ C        | P0       |
| 17  | AC3 browser          | Browser E2E mock | Hai tab mở v1, A lưu trước    | B nhận dialog409, draft B còn         | P0       |

Fixture text tự tạo, thời điểm giao nhau bằng deferred promise/barrier. Không
dùng timestamp để quyết định bản mới hơn; dùng version và thứ tự edit trong editor.

## Evidence

- `evidence/red.log`: TC01 fail trên baseline, PATCH count 0; không phải import error.
- `evidence/green-full.log`: 174 pass toàn frontend; 21 test mới từ bốn file.
- `evidence/e2e.log`: hai E2E Chromium pass; không kết luận về backend thật.
- `evidence/flaky-{19,23,29}.log`: 21/21 với ba order seed, fake timer/deferred.
- `evidence/coverage/coverage-summary.json`: line và branch của đúng hai file mới.
- `evidence/load.json`, `load-samples.json`: 10 wave x120 =1200 mẫu, adapter20ms.
- Mutation: trên nhánh tạm bỏ guard text 1..5000, TC04 phải fail; log được giữ
  ở nhánh nộp nhưng source nộp có đầy đủ validation. Không xóa test để pass.

Commit implementation: `cc332f01f65be6d194fd7adbd4ccab2879b0ee32`.
Commit mutation local: `8062f6011d606bd063464533dbecefbf57ee3c71`, nhánh
`vt019-mutation-validation`; TC04 phát hiện ba lỗi, nên mutant bị kill.
Nhánh nộp không chứa commit mutation. Có thể tái lập mutation trên bản clone
thử nghiệm bằng `git apply vt019/mutation.patch`, chạy `npm test --
src/features/meetings/autosave.test.ts`, rồi hoàn tác bằng
`git apply -R vt019/mutation.patch`. Không áp lên nhánh production.

Không cần test ASR, GPU, audio upload, export cho slice này vì không chạm chúng.
Backend/DB concurrent CAS, auth/session expiry, refresh khi request chưa commit
và đa trình duyệt là residual risks; E2E hiện chỉ có fake HTTP, chưa chứng minh chúng.

## AI review và confidence

Plan trước code và các quyết định bác bỏ ở `docs/frontend/VT-019-plan.md`.
Đã review diff: chỉ nối editor, không thay API hay server version checks.
Test oracle bám yêu cầu: user-visible draft và PATCH body/version, không bám
private field của controller. Cần kết hợp mutation và race schedule với coverage.
