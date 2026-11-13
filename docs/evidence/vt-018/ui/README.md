# Ảnh tiến độ VT-018 — 12/11/2026

Ảnh chụp Playwright từ ứng dụng thật (API + worker + PostgreSQL 16), pipeline fake,
WAV/tài khoản/text tổng hợp, LLM disabled. Không dựng response hay sửa ảnh.
Viewport 1440 × 1000. Code sản phẩm đã kiểm khớp commit `b3c177537d2ad4d5351901c8e9066486e22e4a47`;
lúc chụp HEAD là `e2a0d712dc4900490f69d2672adc4eb0510ddfc2` và các sửa lỗi/harness còn trong working tree.
[Manifest](manifest.json) lưu hash từng source và ảnh để không gán nhầm ảnh cho main cũ.

| Ảnh | Điều được kiểm |
| --- | --- |
| [01-queued.png](01-queued.png) | Job queued 0%, chưa bật worker; bước sắp tới ghi Chờ bắt đầu |
| [02-running.png](02-running.png) | Job running ở giữa chừng, có phần trăm (60% trong snapshot API) |
| [03-succeeded.png](03-succeeded.png) | 100%, có thời gian bắt đầu/kết thúc thật |
| [04-retry-reset.png](04-retry-reset.png) | Bấm Tạo lại tóm tắt sau failed: ID mới, attempt 1, queued từ summarize 5/6 (~83%) |

Test tiếp tục sau ảnh thứ tư tới khi job succeeded, đối chiếu ID từng segment trước/sau
và số nút sửa trên trang transcript: **6 trước = 6 sau**, cùng toàn bộ ID, không trùng.
[Snapshot trạng thái](capture.json) chỉ lưu ID, trạng thái, thời gian; không lưu nội dung transcript.
Nút chạy lại hiện có là Tạo lại tóm tắt. Đây không phải bằng chứng retry toàn bộ ASR
và không chứng minh chất lượng AI thật. Năm bước đã hoàn thành được giữ; không ép progress về 0.

## Chạy lại

Theo phần E2E trong [frontend README](../../../../frontend/README.md): cài npm ci,
Chromium, chuẩn bị PostgreSQL E2E riêng, E2E_DATABASE_URL/SEED_DEMO_PASSWORD,
UV/FFPROBE_BIN nếu chưa ở PATH; giữ cổng 14173/18000 trống. Từ frontend:

```powershell
$env:FAKE_SCENARIO='slow'
npx playwright test --config playwright.evidence.config.ts
```

Config riêng bật E2E_MANUAL_WORKER chỉ cho bộ ảnh; test tự khởi động worker sau ảnh queued,
dừng worker của nó sau từng pha, đổi fake scenario từ summary_fail sang slow để kiểm phục hồi.
Stack E2E bình thường vẫn tự bật worker như trước. Các mốc giờ được lấy khi chạy,
không đóng băng đồng hồ hay sửa DB để tạo trạng thái.

## Các lượt thực hiện

1. Đỏ do partial/pending làm mất nút retry — đã sửa frontend, có test regression.
2. Đỏ do script kỳ vọng 201; contract đúng là 202 — sửa harness.
3. Đỏ do script kỳ vọng retry về 0; summarize đúng là 5/6 — sửa harness.
4. Đạt nhưng running quá sớm; thay điều kiện chụp >=40%.
5. Bản cuối **1 passed**, retries=0, 44.36 giây gồm chuẩn bị stack. Đã xem cả bốn ảnh.

Đây là các lượt phát triển kịch bản khác nhau, không phải năm lượt đo flaky cùng source.
Log đầy đủ/trace để local vì có cookie đăng nhập tổng hợp; manifest có exit code/hash log,
không đưa trace/cookie/audio lên Git.

## Double-click (việc 3)

`RetryDoubleClick.test.tsx` dùng MSW giữ POST chưa trả lời, dblClick nút Tạo lại tóm tắt:
chỉ một POST, Idempotency-Key là UUID, body from_stage=summarize; nút bị khóa đến khi xong,
không tự POST thêm sau khi trả 202. Có trong bộ 301 test/50 file đạt.
Test này chứng minh phía frontend chặn gửi trùng; không thay kiểm concurrency phía backend.
Các file ảnh và test double-click được gộp một commit để dành commit riêng cho lỗi tích hợp
vừa phát hiện và vẫn giữ giới hạn tối đa 5 commit hôm nay.
