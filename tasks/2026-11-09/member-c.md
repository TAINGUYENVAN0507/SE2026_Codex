# 2026-11-09 · Member C: chẩn đoán và sửa 61 s ở 247 client, metric quá tải, tài liệu khớp cấu hình (Đợt 4)

- **Người làm:** C (`@TAINGUYENVAN0507`), nhánh `tainguyen`.
- **Số commit:** 5.
- **Mục tiêu:** hiểu vì sao 247 client cho p95 63 s và sửa bằng số đo; người vận hành thấy quá tải từ `/metrics`; tài liệu không nói hai con số lưu trữ khác nhau; bản đồ yêu cầu → bằng chứng.

| # | Việc | Hash |
|---|---|---|
| 1 | [x] Chẩn đoán: thread và kết nối DB chặn nhau; probe, thử giả thuyết, sửa harness (AD-018, AI-19) | `f614081` |
| 2 | [x] `AdmissionControlMiddleware`, `API_MAX_INFLIGHT`, `API_QUEUE_TIMEOUT_SEC`; test đỏ trước (AD-018) | `a224812` |
| 3 | [x] Đo lại 239, 247 (3 lần mỗi cấu hình) và 40, nêu giới hạn (AD-018, RE-018, AI-19) | `55d032a` |
| 4 | [x] Metric `api_inflight_requests`, `api_admission_rejected_total`; test đỏ trước (RE-018, BE-19) | `a00c151` |
| 5 | [x] Tài liệu lưu trữ khớp cấu hình (test đỏ trước: `rules/` ghi 30 ngày), `docs/evidence/README.md`, ROADMAP | xem `git log` |

## Kết quả và điều còn mở
- 247 client: 247/247 upload, 0 lỗi, cả 6 lần chạy. **Không** tuyên bố đạt p95 ≤ 2,0 s: 1 process p95 tất cả 3,1 đến 3,4 s; 4 process 1,8 đến 1,9 s nhưng p95 chỉ-upload 2,2 đến 2,4 s. Chi tiết và giới hạn: `docs/evidence/load-247/after/README.md`.
- Test đỏ của commit 2 là lỗi import (module chưa có); đỏ theo hành vi là lần chạy 61 s và 150 lỗi trong `probe/exp-a-summary.md`.
- Metric API là theo từng process; chưa gộp khi chạy nhiều process (ghi ở `docs/backend/BE-19.md`).
- Đã sửa harness: lỗi HTTP ở bước create làm luồng chết im lặng, số client ghi nhận lệch 1.
- Cần B: profile `POST /meetings`, `API_WORKERS`, đo lại. DER chưa làm (chưa có SH-01).
