# Bản đồ bằng chứng

Mỗi dòng: yêu cầu của đề, bằng chứng trong repo, trạng thái trung thực. "Không đạt" và "chưa" được ghi nguyên văn. Bằng chứng chỉ là một lần chạy trên một máy trừ khi ghi khác.

Cập nhật 2026-11-12 (`main` đóng băng tại `d9c2d50`, sau #50, #51). Số đo tải 247 và 239 là của 2026-11-11 (thư mục `*-2026-11-11`), 40 client là của 2026-11-12.

## RE-018 (quan sát được, 239 người dùng, lưu 14 ngày)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Log truy được theo `job_id` | `backend/tests/api/test_observability.py`, `pipeline/tests/unit/test_stage_events.py`, `docs/backend/BE-19.md` | Có, trên fake pipeline và DB test |
| Metric có số đo, gồm quá tải và thời gian chờ | `backend/tests/api/test_metrics.py`, `backend/tests/api/test_metrics_multiprocess.py`, `backend/tests/unit/test_admission_control.py`, `docs/backend/BE-19.md` | Có; endpoint metrics gộp mọi process API từ #48 (đo ở 247 client: server đếm 247/247 upload; trước #48 chỉ 54 đến 84/247, `docs/evidence/load-247/after-2026-11-11/README.md`). **Chưa**: `pipeline_stage_duration_seconds` do worker ghi chưa đọc được qua endpoint metrics của API (giao B ngày 2026-11-11) |
| Phản hồi change request trong 20 giờ | `docs/evidence/pr-response-times.md`, `scripts/pr_response_times.py` | **Một phần**: từ 2026-11-06, 5/17 PR có phản hồi của người khác, 4/5 trong 20 giờ; 12 PR merge khi chưa có phản hồi (gồm #47, #48 sau khi nhóm trưởng bỏ yêu cầu review ngày 2026-11-10) |
| Lưu audio 14 ngày chạy thật | `backend/tests/api/test_retention.py`, `docs/privacy/data-policy.md`; test `backend/tests/unit/test_retention_docs_match_config.py` giữ tài liệu khớp cấu hình | Có |
| 239 người dùng đồng thời | `docs/evidence/load-239/` (trước sửa: 1 upload thành công, 101 lỗi 500), `docs/evidence/load-239/analysis.md`, `docs/evidence/load-239/after-2026-11-10/README.md`, `docs/evidence/load-239/after-2026-11-11/README.md` | Chịu được: 239/239 upload, 0 lỗi ở 4 lượt ngày 2026-11-10 và 3 lượt ngày 2026-11-11 (sau #48); p95 upload 2,09 đến 2,37 s (11-10), 3,03 đến 3,25 s (11-11, máy bận hơn). RE-018 không nêu mục tiêu độ trễ |

## AD-018 (sửa đổi được, xóa dữ liệu, 247 người dùng p95 ≤ 2,0 s, lưu vận hành 28 ngày)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Xóa dữ liệu khỏi mọi nơi lưu, cả tài khoản | `backend/tests/api/test_delete_meeting.py`, `test_delete_user.py`, `backend/tests/privacy/test_privacy_canary.py`, `docs/adr/0002-adapter-boundary-and-erasure.md` | Có, trên dữ liệu tổng hợp |
| Log không giữ dữ liệu cá nhân | `backend/tests/privacy/`, `pipeline/tests/unit/test_privacy_canary.py` (tìm ra và sửa rò stderr ở DEBUG) | Có |
| Adapter cho bên thứ ba | `backend/tests/unit/test_adapter_boundary.py`, `docs/pipeline/AI-17.md`, ADR 0002 | Có |
| Tách controller lớn | `backend/tests/unit/test_controller_limits.py`, `docs/adr/0003-controller-size-limit-and-layer-boundary.md`, `docs/backend/AD-018.md` | Có: 100% controller trong `backend/app/api/v1/` ≤ 500 dòng (`meetings.py` 455 dòng, `action_items.py` 452 dòng), không import `app.worker`, có test kiến trúc tự động giữ chốt |
| 247 người dùng, p95 ≤ 2,0 s | `docs/evidence/load-247/diagnosis.md`, `docs/evidence/load-247/after-2026-11-10/README.md`, `docs/evidence/load-247/after-2026-11-11/README.md` | **Không đạt.** 2026-11-11 trên `main` sau #48: 1 process p95 upload 3,16 đến 3,79 s; 4 process (`API_MAX_INFLIGHT=20`) 2,30 đến 2,60 s, 15/15 lượt trên mốc. Phía server 4 process: chỉ 71 đến 82 % upload xong trong 2,0 s, nên thời gian nằm trong app chứ không ở máy sinh tải hay hàng đợi admission. Ngày 11-10, 4 process đạt 10/12 lượt; hôm nay bản trước #48 chạy xen kẽ cũng 2,31 đến 2,37 s, nên kết quả 11-10 không lặp lại được. 0 lỗi ở 21 lượt sau khi harness hết race keep-alive |
| Lưu dữ liệu vận hành 28 ngày | `backend/tests/api/test_retention.py` | Có |
| Phản hồi trong 18 giờ | `docs/evidence/pr-response-times.md` | **Một phần**: 4/5 PR có phản hồi là trong 18 giờ; #44 sau 22,0 giờ |

## VT-018 (tác vụ nền, retry không trùng, pairwise, mutation, 40 người dùng p95 ≤ 1,5 s)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Retry không tạo bản ghi trùng | `backend/tests/reliability/`, `docs/evidence/reliability.md`, `docs/evidence/vt-018/01-red.log` | Có |
| Pairwise | `docs/evidence/vt-018/pairwise.md` | Có |
| Mutation `>` thành `>=` | `docs/evidence/vt-018/mutation.md` | Có |
| AI sinh test, xóa hoặc sửa ≥ 2 test yếu | `docs/evidence/vt-018/ai-tests/README.md`, `backend/tests/ai_raw/vt018_ai_raw.py` (bản thô), `backend/tests/unit/test_vt018_ai_reviewed.py` | Có: sửa 4, xóa 5, thêm 1; mutant bị giết 18/24 ở bản thô, 24/24 sau review. 24/24 không phải phép đo độc lập, vì khi sửa test đã biết trước mutant nào sống |
| 40 người dùng p95 ≤ 1,5 s | `docs/evidence/vt-018/load-40/`, `docs/evidence/vt-018/load-40-before/`, `docs/evidence/vt-018/load-40-after/`, `docs/evidence/vt-018/load-40-2026-11-10/README.md`, `docs/evidence/vt-018/load-40-2026-11-11/README.md`, `docs/evidence/vt-018/load-40-2026-11-12/README.md` | Đạt ở phần lớn lượt, không ổn định: trên `main` đã đóng băng (11-12) 5/6 lượt đạt, 1 lượt p95 upload 1,56 s. Kết quả chia hai mức: quanh 0,5 s và quanh 1,4 đến 1,6 s; thời gian nằm trong app, nguyên nhân chưa rõ. Trước đó: 0,36 đến 0,41 s (11-10, 3/3), 0,56 đến 0,84 s (11-11, 6/6). Fake pipeline, một máy |
| Coverage, flaky | `docs/evidence/vt-018/README.md`; #46: `docs/evidence/vt-018/04-red-ffprobe.log` (5 test upload đỏ trên máy có ffprobe, xanh trên CI) và `backend/tests/integration/test_ffprobe_real.py` | Có; sau #46 kết quả như nhau dù máy có hay không có ffprobe, CI chạy ffprobe thật |

## Chưa làm, không có bằng chứng

- Bản ghi âm họp thật (SH-01): benchmark ASR và DER trên audio họp chưa có.
- Báo cáo cá nhân (PDF) của ba bài nằm ngoài repo theo yêu cầu đề.
