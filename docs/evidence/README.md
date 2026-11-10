# Bản đồ bằng chứng

Mỗi dòng: yêu cầu của đề, bằng chứng trong repo, trạng thái trung thực. "Không đạt" và "chưa" được ghi nguyên văn. Bằng chứng chỉ là một lần chạy trên một máy trừ khi ghi khác.

Cập nhật 2026-11-10 (PR #46 của C; các dòng ghi #46 chỉ đúng sau khi PR đó vào `main`).

## RE-018 (quan sát được, 239 người dùng, lưu 14 ngày)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Log truy được theo `job_id` | `backend/tests/api/test_observability.py`, `pipeline/tests/unit/test_stage_events.py`, `docs/backend/BE-19.md` | Có, trên fake pipeline và DB test |
| Metric có số đo, gồm quá tải và thời gian chờ | `backend/tests/api/test_metrics.py`, `backend/tests/api/test_metrics_multiprocess.py`, `backend/tests/unit/test_admission_control.py`, `docs/backend/BE-19.md` | Có; hỗ trợ gộp số đo qua multiprocess mode (`PROMETHEUS_MULTIPROC_DIR`, `MultiProcessCollector`, `livesum`) khi chạy nhiều process API |
| Phản hồi change request trong 20 giờ | `docs/evidence/pr-response-times.md`, `scripts/pr_response_times.py` | **Một phần**: từ 2026-11-06, 4/15 PR có phản hồi của người khác, 3/4 trong 20 giờ; 10 PR merge khi chưa có phản hồi (gồm #40, #43 của C) |
| Lưu audio 14 ngày chạy thật | `backend/tests/api/test_retention.py`, `docs/privacy/data-policy.md`; test `backend/tests/unit/test_retention_docs_match_config.py` giữ tài liệu khớp cấu hình | Có |
| 239 người dùng đồng thời | `docs/evidence/load-239/` (trước sửa: 1 upload thành công, 101 lỗi 500), `docs/evidence/load-239/analysis.md`, `docs/evidence/load-239/after-2026-11-10/README.md` | Chịu được: 239/239 upload, 0 lỗi ở 4 lượt ngày 2026-11-10; p95 upload 2,09 đến 2,37 s. RE-018 không nêu mục tiêu độ trễ |

## AD-018 (sửa đổi được, xóa dữ liệu, 247 người dùng p95 ≤ 2,0 s, lưu vận hành 28 ngày)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Xóa dữ liệu khỏi mọi nơi lưu, cả tài khoản | `backend/tests/api/test_delete_meeting.py`, `test_delete_user.py`, `backend/tests/privacy/test_privacy_canary.py`, `docs/adr/0002-adapter-boundary-and-erasure.md` | Có, trên dữ liệu tổng hợp |
| Log không giữ dữ liệu cá nhân | `backend/tests/privacy/`, `pipeline/tests/unit/test_privacy_canary.py` (tìm ra và sửa rò stderr ở DEBUG) | Có |
| Adapter cho bên thứ ba | `backend/tests/unit/test_adapter_boundary.py`, `docs/pipeline/AI-17.md`, ADR 0002 | Có |
| Tách controller lớn | `backend/tests/unit/test_controller_limits.py`, `docs/adr/0003-controller-size-limit-and-layer-boundary.md`, `docs/backend/AD-018.md` | Có: 100% controller trong `app/api/v1/` ≤ 500 dòng (`meetings.py` 455 dòng, `action_items.py` 452 dòng), không import `app.worker`, có test kiến trúc tự động giữ chốt |
| 247 người dùng, p95 ≤ 2,0 s | `docs/evidence/load-247/diagnosis.md`, `docs/evidence/load-247/after-2026-11-10/README.md`, `docs/evidence/load-247/client-procs/README.md` | **Cấu hình mặc định (1 process) không đạt**: p95 upload 2,25 đến 3,75 s, 14/14 lượt trên 2,0 s. **4 process (`API_MAX_INFLIGHT=20`) đạt ở 10/12 lượt**: p95 upload 1,08 đến 2,18 s, sát mốc khi máy bận; không ghi là đạt chắc chắn. 6 lỗi `RemoteProtocolError`/6.669 upload, do harness (kết nối rảnh đúng 5 s, timeout keep-alive của uvicorn) |
| Lưu dữ liệu vận hành 28 ngày | `backend/tests/api/test_retention.py` | Có |
| Phản hồi trong 18 giờ | `docs/evidence/pr-response-times.md` | **Một phần**: 3/4 PR có phản hồi là trong 18 giờ; #44 sau 22,0 giờ |

## VT-018 (tác vụ nền, retry không trùng, pairwise, mutation, 40 người dùng p95 ≤ 1,5 s)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Retry không tạo bản ghi trùng | `backend/tests/reliability/`, `docs/evidence/reliability.md`, `docs/evidence/vt-018/01-red.log` | Có |
| Pairwise | `docs/evidence/vt-018/pairwise.md` | Có |
| Mutation `>` thành `>=` | `docs/evidence/vt-018/mutation.md` | Có |
| 40 người dùng p95 ≤ 1,5 s | `docs/evidence/vt-018/load-40/`, `docs/evidence/vt-018/load-40-before/`, `docs/evidence/vt-018/load-40-after/`, `docs/evidence/vt-018/load-40-2026-11-10/README.md` | Đạt: p95 upload 0,36 đến 0,41 s ở 3/3 lượt ngày 2026-11-10; fake pipeline, một máy |
| Coverage, flaky | `docs/evidence/vt-018/README.md`; #46: `docs/evidence/vt-018/04-red-ffprobe.log` (5 test upload đỏ trên máy có ffprobe, xanh trên CI) và `backend/tests/integration/test_ffprobe_real.py` | Có; sau #46 kết quả như nhau dù máy có hay không có ffprobe, CI chạy ffprobe thật |

## Chưa làm, không có bằng chứng

- Bản ghi âm họp thật (SH-01): benchmark ASR và DER trên audio họp chưa có.
- Báo cáo cá nhân (PDF) của ba bài nằm ngoài repo theo yêu cầu đề.
