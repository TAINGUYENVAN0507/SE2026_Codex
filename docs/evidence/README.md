# Bản đồ bằng chứng

Mỗi dòng: yêu cầu của đề, bằng chứng trong repo, trạng thái trung thực. "Không đạt" và "chưa" được ghi nguyên văn. Bằng chứng chỉ là một lần chạy trên một máy trừ khi ghi khác.

Cập nhật 2026-11-09.

## RE-018 (quan sát được, 239 người dùng, lưu 14 ngày)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Log truy được theo `job_id` | `backend/tests/api/test_observability.py`, `pipeline/tests/unit/test_stage_events.py`, `docs/backend/BE-19.md` | Có, trên fake pipeline và DB test |
| Metric có số đo, gồm quá tải | `backend/tests/api/test_metrics.py`, `backend/tests/unit/test_admission_control.py` | Có; metric API là theo từng process, chưa gộp khi chạy nhiều process |
| Lưu audio 14 ngày chạy thật | `backend/tests/api/test_retention.py`, `docs/privacy/data-policy.md`; test `backend/tests/unit/test_retention_docs_match_config.py` giữ tài liệu khớp cấu hình | Có |
| 239 người dùng đồng thời | `load-239/` (trước sửa: 1 upload thành công, 101 lỗi 500), `load-239/analysis.md` (sau sửa: 239/239, p95 tất cả 3,7 s) | Hết lỗi; RE-018 không nêu mục tiêu độ trễ |

## AD-018 (sửa đổi được, xóa dữ liệu, 247 người dùng p95 ≤ 2,0 s, lưu vận hành 28 ngày)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Xóa dữ liệu khỏi mọi nơi lưu, cả tài khoản | `backend/tests/api/test_delete_meeting.py`, `test_delete_user.py`, `backend/tests/privacy/test_privacy_canary.py`, `docs/adr/0002-adapter-boundary-and-erasure.md` | Có, trên dữ liệu tổng hợp |
| Log không giữ dữ liệu cá nhân | `backend/tests/privacy/`, `pipeline/tests/unit/test_privacy_canary.py` (tìm ra và sửa rò stderr ở DEBUG) | Có |
| Adapter cho bên thứ ba | `backend/tests/unit/test_adapter_boundary.py`, `docs/pipeline/AI-17.md`, ADR 0002 | Có |
| Tách controller lớn | `meetings.py` còn 1216 dòng (từ 2412); đợt 4 tách tiếp | Một phần |
| 247 người dùng, p95 ≤ 2,0 s | `load-247/diagnosis.md`, `load-247/after/README.md` | **Chưa đạt theo cách tính chặt**: 1 process p95 tất cả 3,1 đến 3,4 s; 4 process 1,8 đến 1,9 s tính cả poll nhưng 2,2 đến 2,4 s chỉ tính upload. Hết lỗi |
| Lưu dữ liệu vận hành 28 ngày | `backend/tests/api/test_retention.py` | Có |

## VT-018 (tác vụ nền, retry không trùng, pairwise, mutation, 40 người dùng p95 ≤ 1,5 s)

| Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|
| Retry không tạo bản ghi trùng | `backend/tests/reliability/`, `docs/evidence/reliability.md`, `docs/evidence/vt-018/01-red.log` | Có |
| Pairwise | `docs/evidence/vt-018/pairwise.md` | Có |
| Mutation `>` thành `>=` | `docs/evidence/vt-018/mutation.md` | Có |
| 40 người dùng p95 ≤ 1,5 s | `docs/evidence/vt-018/load-40/`, `docs/evidence/vt-018/load-40-before/`, `docs/evidence/vt-018/load-40-after/` | Đạt: 0,65 s sau thay đổi mới nhất; fake pipeline, một máy |
| Coverage, flaky | `docs/evidence/vt-018/README.md` | Có |

## Chưa làm, không có bằng chứng

- Bản ghi âm họp thật (SH-01): benchmark ASR và DER trên audio họp chưa có.
- Chạy thật container web trong CI (nginx khởi động): giao cho A, `tasks/2026-11-09/member-a.md`.
- Báo cáo cá nhân (PDF) của ba bài nằm ngoài repo theo yêu cầu đề.
