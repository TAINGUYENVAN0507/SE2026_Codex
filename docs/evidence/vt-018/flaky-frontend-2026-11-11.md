# Chạy lặp frontend — VT-018 — 11/11/2026

## Phạm vi và nguồn

- Source commit: `986e2b8d9e6eb74d14b06646c5f85b73167995d3`; không thay source giữa các lượt của cùng đợt đo.
- Node v24.13.0, Windows, Chromium, PostgreSQL 16 riêng trên loopback.
- API/worker/backend thật; `PIPELINE_BACKEND=fake`, `FAKE_SCENARIO=slow`.
  User/WAV/dữ liệu tổng hợp, không gọi model AI hoặc LLM bên ngoài.
- Playwright `retries: 0`. Không tự chạy lại một test lỗi rồi coi là lượt xanh.

## Lệnh

Chạy trong `frontend/` trên môi trường E2E theo README. PowerShell máy này dùng
`npx.cmd`/`npm.cmd` thay `npx`/`npm` do policy; script không thay đối số lệnh.

```text
npx vitest run src/pages/BusyUpload.test.tsx src/features/jobs/BusyPolling.test.tsx src/features/meetings/BusyEdits.test.tsx src/features/audio/uploadBusyTimer.test.ts src/features/jobs/JobTimes.test.tsx
```

Lệnh unit được gọi 20 process Vitest mới liên tiếp. Sau đó gọi `npm run e2e`
3 lần liên tiếp với `FAKE_SCENARIO=slow`, cùng database test riêng; mỗi lượt
tự bật/migrate/seed/build API, worker, preview rồi tự dừng các process đó.
Ba lượt E2E là bộ mặc định slow của lệnh được giao, không phải 3 lần cả ma trận
permanent/transient_once/summary_fail. Các scenario đó đã có bằng chứng riêng
từ đợt trước; không tính kết quả cũ vào số đo hôm nay.

## Nhóm unit được giao

| Lượt | Test đạt | Exit code | Thời gian (s) |
|---|---:|---:|---:|
| 1 | 18 | 0 | 5.48 |
| 2 | 18 | 0 | 3.75 |
| 3 | 18 | 0 | 3.84 |
| 4 | 18 | 0 | 3.80 |
| 5 | 18 | 0 | 3.72 |
| 6 | 18 | 0 | 3.70 |
| 7 | 18 | 0 | 3.67 |
| 8 | 18 | 0 | 3.78 |
| 9 | 18 | 0 | 3.70 |
| 10 | 18 | 0 | 3.80 |
| 11 | 18 | 0 | 3.86 |
| 12 | 18 | 0 | 3.75 |
| 13 | 18 | 0 | 4.22 |
| 14 | 18 | 0 | 3.80 |
| 15 | 18 | 0 | 3.84 |
| 16 | 18 | 0 | 3.88 |
| 17 | 18 | 0 | 3.73 |
| 18 | 18 | 0 | 3.89 |
| 19 | 18 | 0 | 3.64 |
| 20 | 18 | 0 | 3.67 |

Kết quả cuối: **0/20 lượt lỗi**, mỗi lượt 18 test. Đây là 18 test chạy lại
20 lần (360 lần thực thi), không phải 360 test khác nhau.

## E2E mặc định

| Lượt | Test đạt | Exit code | Thời gian (s) |
|---|---:|---:|---:|
| 1 | 24 | 0 | 308.73 |
| 2 | 24 | 0 | 314.75 |
| 3 | 24 | 0 | 309.14 |

Kết quả cuối: **0/3 lượt lỗi**, mỗi lượt 24 E2E (72 lần thực thi, 24 test khác
nhau). Không đổi test hoặc code chức năng chỉ để tăng số lần pass.

## Minh bạch và giới hạn

- Tổng mọi attempt đã ghi: 20 lượt unit, 0 lượt lỗi;
  3 lượt E2E, 0 lượt lỗi. JSON giữ từng exit code, thời
  điểm UTC, thời gian chạy và SHA256 log; không chỉ ghi kết quả lần cuối.
- Script điều phối QA ngoài Git lúc đầu kỳ vọng nhầm 19 test; Vitest thực tế có 18 trong năm file
  được giao. Guard của harness dừng trước E2E sau khi 20 lệnh Vitest đều exit 0.
  Đã đối chiếu số đếm và tiếp tục E2E trên đúng commit, giữ nguyên 20 log đó;
  không tính lỗi bộ đếm của script QA thành test flaky và không giấu test lỗi.
- Cảnh báo worker native Windows `os.killpg`: 3 lần trong log E2E.
  Đây là giới hạn đã biết của pipeline; UI/API pass không chứng minh cleanup
  subprocess đúng trên mọi nền tảng. Không sửa module của C trong task này.
- 0 lỗi trong số lượt đã đo không chứng minh test không bao giờ flaky.
  Một máy local và pipeline fake không thay CI hoặc kiểm chất lượng AI thật.
- [JSON tổng hợp](flaky-frontend-2026-11-11.json) được commit; log/trace/report
  đầy đủ ở thư mục QA ngoài Git. Database/container test được dọn sau kiểm tra.
