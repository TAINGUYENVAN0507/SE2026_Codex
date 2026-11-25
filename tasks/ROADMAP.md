# Kế hoạch còn lại

> Cập nhật 2026-11-25. Trạng thái yêu cầu đọc từ `main` tại `70b527a` (sau #74 và #75). Nhóm trưởng cập nhật file này mỗi khi phân công.

## Tiếp tục vào ngày sau

1. Đọc `tasks/<ngày gần nhất>/member-*.md`: ô nào chưa tick thì ghi "chuyển từ <ngày>" sang file mới.
2. Lấy việc của đợt kế tiếp ở mục [Lịch](#lịch), tạo `tasks/<ngày>/member-{a,b,c}.md`; số commit mỗi người theo yêu cầu của nhóm trưởng ngày đó (Đợt 1–4: 5, Đợt 5: 10).
3. Đánh dấu trạng thái ở mục [Yêu cầu](#yêu-cầu-repo-phải-đáp-ứng) và sửa ngày cập nhật ở đầu file.
4. Đưa file phân công lên `main` qua PR, như các ngày trước.

## Vì sao có đợt này

Nhóm trưởng có 3 bài cá nhân phân tích trên chính repo này. Bài PDF là của cá nhân, không nằm trong repo. File này chỉ ghi phần **sản phẩm** phải có. A và B làm việc của sản phẩm, không viết hộ artefact của bài cá nhân.

| Mã | Trọng tâm | Tham số |
|---|---|---|
| RE-018 | Người quản lý cần báo cáo kiểm chứng được; Observability: log, metric, truy nguyên nhân | 239 người dùng đồng thời, lưu 14 ngày, 20 giờ phản hồi change request |
| AD-018 | Xóa dữ liệu cá nhân trải trên nhiều module và log; adapter boundary cho bên thứ ba; controller quá lớn; Modifiability | 247 đồng thời, p95 ≤ 2.0 s, dữ liệu vận hành 28 ngày, 18 giờ phản hồi |
| VT-018 | Tác vụ dài chạy nền và hiện tiến độ; retry tạo bản ghi trùng; pairwise; mutation `>` thành `>=` | 40 đồng thời, p95 ≤ 1.5 s |

## Tham số

Quy ước của nhóm (nhóm trưởng giao quyền chọn ngày 2026-11-09, giữ 14 và 28), để hai con số lưu trữ của RE-018 và AD-018 không mâu thuẫn:

| Biến | Mặc định | Áp dụng cho |
|---|---|---|
| `AUDIO_RETENTION_DAYS` | 14 | Audio và artifact của job (artifact chứa transcript dạng JSON) |
| `OPERATIONAL_RETENTION_DAYS` | 28 | `idempotency_keys`, log. Không chứa nội dung cuộc họp |

Transcript trong DB giữ tới khi người dùng xóa. Hai giá trị đặt qua biến môi trường nên đổi được, không sửa code.

Không ghi hệ thống chịu được 239 hay 247 người dùng khi chưa đo. Mức đo bắt buộc là 40 (đợt 2); đo ở 239 và 247 ở đợt 3.

**Phản hồi:** trong các đợt này, PR được review trong 18 giờ kể từ lúc mở (đáp ứng cả 18 và 20 giờ).

**Review từ 2026-11-10:** nhóm trưởng quyết định PR không cần chờ review của thành viên khác. Nhóm trưởng tự review diff, chờ CI xanh rồi merge, theo `rules/git-workflow.md`. Đề BT3 ghi "Không merge nếu nhóm chưa review", BT1 ghi "mỗi Pull Request phải có review và test evidence". Vì vậy, từ #46, `docs/evidence/pr-response-times.md` sẽ ghi PR là merge khi chưa có phản hồi của người khác.

## Field log

Dùng chung cho API, worker và pipeline, để lọc được theo một `job_id`:

`event`, `job_id`, `meeting_id`, `request_id`, `worker_id`, `stage`, `attempt`, `error_code`, `duration_sec`, `status`.

Không có field nào chứa tiêu đề, tên file, text transcript hay đường dẫn tuyệt đối.

## Task ID mới

Commit của C trong các đợt này ghi thêm mã bài, ví dụ `(BE-17, VT-018)`.

| ID | Việc |
|---|---|
| BE-17 | Rerun không trùng bản ghi; tiến độ không tụt; thời gian job thật |
| BE-18 | Service xóa dữ liệu trên mọi nơi lưu; xóa cả tài khoản |
| BE-19 | Log JSON có job id; `/metrics` |
| AI-17 | Test khóa adapter boundary |
| AI-18 | Pipeline ghi sự kiện có cấu trúc |
| AI-19 | Harness tải và kết quả đo |
| FE-18 | Evidence trong export và trên giao diện |
| FE-19 | Xóa cuộc họp, hạn lưu trữ, audio hết hạn |
| FE-20 | Thanh tiến độ |

## Yêu cầu repo phải đáp ứng

Hiện trạng đọc từ `main` tại `70b527a` ngày 2026-11-25 (từ 11-12 chỉ sửa lỗi; sau hạn nộp 11-14, chỉ sửa lỗi, thêm test và bằng chứng). ✓ đã có · ◐ một phần · ✗ chưa có. Số đo tải: một máy, pipeline fake; chi tiết và giới hạn ở [`docs/evidence/README.md`](../docs/evidence/README.md). Bảng theo code ngày 11-06 (`53f753b`) đã thay bằng bảng này; lịch sử xem git.

### RE-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Tóm tắt dẫn về đúng đoạn audio | ✓ Key point, quyết định và action item đều có link evidence (`EvidenceLinks.tsx`, `RemoteTasks.tsx`) | FE-18 | A | 1 |
| File export kiểm chứng được | ✓ TXT, MD, JSON in evidence (`backend/app/services/export/serializers.py`); E2E `frontend/e2e/flows/export-evidence.spec.ts` | FE-18, BE-05 | A, B | 1 |
| Log truy được theo job | ✓ `setup_logging()` ở API và worker; `backend/tests/api/test_observability.py` | BE-19, AI-18 | B, C | 1 |
| Metric có số đo | ✓ `/metrics`; quá tải và thời gian chờ admission; bucket có mốc 1,5 và 2,0 s (#46) | BE-19 | B, C | 1, 4, 5 |
| Thời lượng từng stage trong metric | ✓ #51 (2026-11-12): `api` và `worker` dùng chung `PROMETHEUS_MULTIPROC_DIR`; test subprocess và `smoke_compose.py` kiểm `pipeline_stage_duration_seconds_count` > 0, compose-smoke xanh trên CI | BE-19 | B | 2, 6 |
| Metric đúng khi chạy nhiều process API | ✓ `PROMETHEUS_MULTIPROC_DIR`, `MultiProcessCollector`, `livesum` gộp đủ mọi process API | BE-19 | B | 5 |
| Runbook truy nguyên nhân, có thời gian đo thật | ✓ Diễn tập 2 sự cố trên Compose đo thời gian thật tại `docs/backend/runbook-drill-2026-11-10.md`, bổ sung runbook `docs/backend/BE-19.md` | BE-19 | B | 5 |
| Lưu 14 ngày chạy thật | ✓ Worker gọi `run_retention_cleanup`; `backend/tests/api/test_retention.py`; test giữ tài liệu khớp cấu hình | BE-14 | B, C | 1, 4 |
| 239 người dùng đồng thời | Xem bảng tải bên dưới | AI-19 | C | 3–5 |
| Phản hồi change request trong 20 giờ | ◐ `docs/evidence/pr-response-times.md` (sinh lại 11-25): từ 11-06, 15/44 PR có phản hồi của người khác, 11/15 trong 20 giờ; 29 PR merge khi chưa có phản hồi. Đợt 14: B review #74 sau 12,4 giờ, A review #75 sau 0,5 giờ. Đợt 13: B chưa mở PR; #72 chỉ có review của C. Đợt 12: B approve #69 sau 8,0 giờ; A review #70 sau 63,3 giờ (quá hạn, finding đúng). Đợt 11: B review #66 sau 31,4 giờ (quá hạn); A không review #67. Review chéo Đợt 9: A review #61 sau 4,4 giờ; B review #64 sau khoảng 1 giờ; B không review #60 (phản hồi đầu tiên là của C sau 20,2 giờ). #56, #57 chờ 44 giờ | | A, B, C | 9, 10 |

### AD-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Xóa khỏi mọi nơi lưu | ✓ `backend/app/services/erasure/`; `test_delete_meeting.py` (SQLite); canary: `idempotency_keys` không còn tiêu đề; 11-13: `tests/integration/test_erasure_postgres.py` trên Postgres đã migrate, bảng nơi lưu → test ở `docs/evidence/ad-018/README.md`. Log Docker chưa có test | BE-18 | B | 1 |
| Xóa được cả tài khoản | ✓ `DELETE /auth/me` và giao diện xóa tài khoản (#42) | BE-18 | B, A | 2 |
| Log không giữ dữ liệu cá nhân | ✓ từ 11-16: canary ở API, worker, pipeline; uvicorn `--no-access-log` có test server thật (#61); nginx không ghi query string (#64, kiểm bằng CI). Dưới 247 client: 0 dòng log có query string. Trước 11-16 log container từng ghi query string | BE-18, BE-19, AI-18, FE-19 | A, B, C | 1, 3, 10 |
| Adapter cho bên thứ ba | ✓ `engines/`, `llm/` có interface và bản fake | | C | |
| Có cơ chế cưỡng chế boundary | ✓ Test AST, `docs/pipeline/AI-17.md` | AI-17 | C | 1 |
| Tách controller quá lớn | ✓ 100% controller trong `app/api/v1/` $\le 500$ dòng (`meetings.py` 455 dòng, `action_items.py` 452 dòng); upload tách sang service; test kiến trúc `test_controller_limits.py` giữ chốt | BE-12 | B | 2–5 |
| ADR | ✓ `docs/adr/0001-asr.md`, `0002-adapter-boundary-and-erasure.md`, `0003-controller-size-limit-and-layer-boundary.md` | | C, B | 3, 5 |
| 247 đồng thời, p95 ≤ 2,0 s | Xem bảng tải bên dưới | AI-19, BE-12 | B, C | 3–5 |
| Lưu dữ liệu vận hành 28 ngày | ✓ `OPERATIONAL_RETENTION_DAYS=28`, `backend/tests/api/test_retention.py` | BE-14 | B | 1 |
| Phản hồi trong 18 giờ | ◐ Như dòng 20 giờ ở RE-018: 6/8 PR có phản hồi là trong 18 giờ; #44 sau 22,0 giờ, #60 sau 20,2 giờ; #56, #57 chờ 44 giờ | | A, B, C | 9, 10 |

### VT-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Job chạy nền, poll trạng thái | ✓ `POST /meetings`, `GET /jobs/{id}`, poll 2 s | | | |
| Retry không tạo bản ghi trùng | ✓ PR #35 (merge 11-07, không có review trên GitHub) | BE-17 | C | 1 |
| Tiến độ không tụt | ✓ PR #35 | BE-17 | C | 1 |
| Có thời gian bắt đầu và kết thúc | ✓ PR #35; giao diện hiện thời gian đã chạy | BE-17, FE-20 | C, A | 1 |
| Giao diện hiện tiến độ | ✓ PR #34 | FE-20 | A | 1 |
| Test pairwise | ✓ `docs/evidence/vt-018/pairwise.md` | | C | 2 |
| Mutation `>` thành `>=` có test bắt được | ✓ `docs/evidence/vt-018/mutation.md` | | C | 2 |
| AI sinh test, xóa hoặc sửa ≥ 2 test yếu | ✓ `docs/evidence/vt-018/ai-tests/`: sửa 4, xóa 5, thêm 1; mutant bị giết 18/24 → 24/24 (sau review, không độc lập) | | C | 7 |
| Coverage, flaky | ✓ `docs/evidence/vt-018/README.md`; #46: 5 test upload từng đỏ trên máy có ffprobe, xanh trên CI, nay ra cùng kết quả ở mọi máy | | C | 2, 5 |
| Bằng chứng đọc được trên GitHub | ✓ 11-15: `backend/tests/unit/test_docs_utf8.py` chặn file UTF-16 trong `docs/`, `tasks/` (đã gặp ở #54, #56) | | C | 9 |
| Tải 40 đồng thời, p95 ≤ 1.5 s | Xem bảng tải bên dưới | AI-19 | C | 2–5 |
| README chạy test của bài | ✓ `docs/evidence/vt-018/README.md` | | C | 2 |

### Tải (cập nhật sau mỗi lần đo)

Đo ngày 2026-11-11 trên `main` `1f9d1ca` (sau #47, #48), một máy 12 CPU, pipeline fake, tải dạng barrier, 4 process sinh tải (40 client: 1). Harness mới: client đóng kết nối rảnh sau 1 s; có số phía server khi chạy nhiều process. A/B xen kẽ cho thấy thay đổi harness không làm số khác đi. Chi tiết: `docs/evidence/load-247/after-2026-11-11/README.md`, `docs/evidence/load-239/after-2026-11-11/README.md`, `docs/evidence/vt-018/load-40-2026-11-11/README.md`. Đo lại ngày 2026-11-15 trên `115c905` (Đợt 9): `docs/evidence/load-247/pinned-2026-11-15/README.md`, `docs/evidence/vt-018/load-40-2026-11-15/README.md`.

| Mốc | Cấu hình | Kết quả | Trạng thái |
|---|---|---|---|
| VT-018: 40 đồng thời, p95 ≤ 1,5 s | 1 process API | 11-25 trên `70b527a`, có tìm kiếm: 6/6 đạt, p95 upload 0,39 đến 0,69 s (`docs/evidence/vt-018/load-40-2026-11-25/README.md`). 11-24 trên `b35e06f`, có tìm kiếm, thư mục lưu trống: 6/6 đạt, p95 upload 0,43 đến 0,55 s (`docs/evidence/vt-018/load-40-2026-11-24/README.md`). 11-23 trên `5c29101`, có tìm kiếm, thư mục lưu trống và thật xen kẽ: 6/6 đạt, p95 upload 0,39 đến 0,66 s (`docs/evidence/vt-018/load-40-2026-11-23/README.md`). 11-19 trên `006fd8c`, có 4 lượt tìm kiếm mỗi client: 6/6 đạt, p95 upload 0,38 đến 0,49 s (`docs/evidence/vt-018/load-40-2026-11-19/README.md`). 11-17 trên `1dc6b5c`: 6/6 đạt, p95 upload 0,41 đến 0,55 s (`docs/evidence/vt-018/load-40-2026-11-17/README.md`). 11-16 trên `3ed9c0d`: 12/12 đạt, p95 upload 0,38 đến 0,64 s; thư mục đầy/rỗng xen kẽ, đổi thứ tự giữa các vòng: thứ tự không phải lý do, thư mục đầy trung bình chậm hơn 0,08 s ở 4/6 vòng (`docs/evidence/vt-018/load-40-2026-11-16/README.md`). 11-15 trên `115c905`: 16/16 đạt, p95 upload 0,34 đến 0,73 s; xen kẽ `synchronous_commit` bật/tắt và thư mục lưu đầy/rỗng/RAM: fsync khi commit và ghi đĩa không giải thích được mức chậm; thư mục lưu đầy (18.080 thư mục con) chậm hơn khoảng 0,13 s (`docs/evidence/vt-018/load-40-2026-11-15/README.md`). 11-13 trên `a75853d`: 12/12 đạt, p95 upload 0,36 đến 0,87 s; xen kẽ ffprobe thật và giả, ffprobe không giải thích được mức chậm (`docs/evidence/vt-018/load-40-2026-11-13/README.md`). 11-12 trên `d9c2d50`: 5/6, 1 lượt 1,56 s; hai mức quanh 0,5 s và 1,4 đến 1,6 s. 11-11: 6/6. Gộp 10 ngày 81/82 | ◐ đạt 81/82 lượt, 1 lượt không đạt chưa rõ nguyên nhân |
| RE-018: 239 đồng thời (không có mục tiêu độ trễ) | 1 process API | 239/239 upload, 0 lỗi, 3 lượt; p95 upload 3,03 đến 3,25 s | ✓ chịu được |
| AD-018: 247 đồng thời, p95 ≤ 2,0 s | 1 process API (mặc định) | 11-24 trên `b35e06f`, có tìm kiếm, thư mục lưu trống: 2,68 đến 3,00 s, 3/3 trên mốc (`docs/evidence/load-247/procs-2026-11-24/README.md`). 11-19 trên `006fd8c`, có tìm kiếm: 2,28 đến 3,02 s, 3/3 trên mốc (`docs/evidence/load-247/search-2026-11-19/README.md`). 11-17 trên `1dc6b5c`: 2,12 đến 2,29 s, 3/3 trên mốc (`docs/evidence/load-247/api-log-2026-11-17/README.md`). 11-16 trên `3ed9c0d`: 2,32 đến 3,24 s, 3/3 trên mốc; process uvicorn dùng 1,10 đến 1,15 CPU (trần của một process Python có GIL), event loop 0,28 đến 0,32 (`docs/evidence/load-247/event-loop-2026-11-16/README.md`). 11-15 trên `115c905`: p95 upload 2,09 đến 2,75 s, 6/6 lượt trên mốc; ghim máy sinh tải sang nhân riêng không đổi kết quả (`docs/evidence/load-247/pinned-2026-11-15/README.md`). 11-11: 3,16 đến 3,79 s, 3/3 trên mốc (11-10: 14/14) | ✗ |
| AD-018: 247 đồng thời, p95 ≤ 2,0 s | 2 process API | 11-25, trước/sau bản sửa N+1 xen kẽ: trước (`b35e06f`) 4/4 đạt (1,72 đến 1,95 s), sau (`70b527a`) 1/4 (1,76 đến 2,45 s); `GET /meetings` đo riêng nhanh hơn sau bản sửa, phần chậm chưa rõ nguyên nhân (`docs/evidence/load-247/n-plus-one-2026-11-25/README.md`). 11-23 trên `5c29101`, thư mục lưu trống, xen kẽ ABBA ABBA: không tìm kiếm 3/4 đạt (1,38 đến 2,01 s), có tìm kiếm 4/4 đạt (1,61 đến 1,89 s); chênh trung bình khoảng 0,1 s, nhỏ hơn dao động (`docs/evidence/load-247/search-ab-2026-11-23/README.md`). 11-19 trên `006fd8c`, có tìm kiếm: 2/3 đạt (1,48 và 1,70 s; 1 lượt 2,52 s). 11-17 trên `1dc6b5c`: 3/3 đạt, 1,38 đến 1,41 s. 11-16 trên `3ed9c0d`: 3/3 đạt, p95 upload 1,50 đến 1,60 s; mỗi process khoảng 1,0 CPU. Đạt ở hai ngày khi không có tìm kiếm, chưa đo trên Compose | ◐ đạt ở 2 ngày, 2/3 khi có tìm kiếm (11-19), 7/8 khi xen kẽ (11-23) |
| AD-018: 247 đồng thời, p95 ≤ 2,0 s | 4 process API, `API_MAX_INFLIGHT=20` | 11-24 trên `b35e06f`, có tìm kiếm, thư mục lưu trống: 3/3 đạt, 1,28 đến 1,37 s. 11-19 trên `006fd8c`, có tìm kiếm: 3/3 đạt, 1,10 đến 1,15 s. 11-17 trên `1dc6b5c`: 3/3 đạt, 1,01 đến 1,11 s. 11-16 trên `3ed9c0d`: 3/3 đạt, 1,04 đến 1,39 s. 11-15 trên `115c905`: 9/9 lượt đạt, p95 upload 1,00 đến 1,37 s. A/B với app 11-11 (`1f9d1ca`): 1,05 đến 1,18 s, nên chênh với 11-11 không do code. 11-11: 2,30 đến 2,60 s, 15/15 lượt trên mốc. 11-10: 10/12 đạt | ◐ đạt ở 11-10, 11-15, 11-16, 11-17, 11-19 và 11-24, không đạt ở 11-11; nguyên nhân chênh giữa các ngày chưa rõ |

0 lỗi ở 21 lượt 247 client ngày 11-11 (5.187 upload). Phía server 4 process: thời gian nằm trong xử lý upload, không ở hàng đợi admission (95 đến 97 % request vào trong ≤ 1,5 s). Phía server 1 process: 2/3 lượt có ≥ 99,6 % upload ≤ 2,0 s, trong khi client chỉ thấy 49 đến 58 %, nên phần chậm nằm trước middleware (một event loop). Ngày 11-15 kiểm phần "máy sinh tải": nó chỉ dùng 0,27 đến 0,71 CPU, và ghim nó sang nhân riêng không đổi kết quả, nên phần chậm không ở máy sinh tải. 0 lỗi ở 18 lượt 247 client ngày 11-15 (4.446 upload).

## Lịch

Đợt 1 là `tasks/2026-11-06/`. Các đợt sau chưa gắn ngày; tạo file phân công khi tới lượt.

### Đợt 2 (giao ngày 2026-11-07: `tasks/2026-11-07/`; phần C đã xong)

| Member | Commit | Việc |
|---|---|---|
| A | 1 | E2E tóm tắt và export trên stack thật (cần BE-05) |
| A | 2 | Evidence trong file export tải về khớp với giao diện (E2E) |
| A | 3 | Giao diện xóa tài khoản (cần BE-18 phần tài khoản) |
| A | 4 | Audio hết hạn: E2E trọn luồng (cần BE-14) |
| A | 5 | `docs/demo/ux-checklist.md`, ảnh chụp, kịch bản demo |
| B | 1 | `DELETE /auth/me` xóa toàn bộ dữ liệu của người dùng, sinh lại `openapi.json` (BE-18) |
| B | 2 | Lưu `outcome.timings`, thêm metric thời lượng từng stage (BE-19) |
| B | 3 | Tách route action item khỏi `meetings.py`, không đổi hành vi, kiểm bằng test drift của OpenAPI |
| B | 4 | Dockerfile của API và web, nginx (BE-16) |
| B | 5 | Compose đủ `db`, `api`, `worker`, `web` có healthcheck (BE-16) |
| C | 1 | Pairwise cho `POST /jobs`: `from_stage`, trạng thái job trước, có chỉnh sửa, `Idempotency-Key`; sinh bộ test bằng công cụ, commit bảng sinh ra (BE-17, VT-018) |
| C | 2 | Gom 4 chỗ `attempt < max_attempts` (`jobs.py:59`, `meetings.py:2068`, `reaper.py:104`, `runner.py:408`) thành property `Job.can_retry`, dùng `max_attempts > attempt`. Đặt ở model vì API không được phụ thuộc vào worker. Test RT-04 đúng ở biên 3/3 (BE-17, VT-018) |
| C | 3 | Script mutation trên nhánh tạm: đổi `>` thành `>=`, chứng minh có test bắt được, không để lại trong nhánh nộp. Thử thêm `preprocess.py:173`; nếu mutant sống thì bổ sung test (BE-17, VT-018) |
| C | 4 | Harness tải 40 đồng thời trên Postgres thật và fake pipeline, có `env.json`, so với p95 1.5 s; ghi rõ giới hạn của phép đo, gồm việc worker chạy mỗi lúc 1 job (AI-19, VT-018) |
| C | 5 | Coverage line và branch, kiểm 2 nguy cơ flaky (time, order hoặc concurrency), README chạy test ở `docs/evidence/vt-018/README.md` (BE-17, VT-018) |

### Đợt 3

| Member | Việc |
|---|---|
| A | Bug bash giao diện, ảnh demo, sửa lỗi từ người dùng thử |
| B | Tách tiếp `meetings.py` theo nhóm route; `tests/reliability`, `tests/privacy`, `docs/evidence/` (BE-15); `make` |
| C | ADR `0002` (adapter boundary và xóa dữ liệu); đo tải ở 239 và 247; đồng bộ `README.md`, `structure/`, `rules/` với hiện trạng; DER nếu có SH-01 |

### Đợt 3 (giao ngày 2026-11-08: `tasks/2026-11-08/`)

Kết quả phần C: ADR 0002, test canary pipeline (sửa rò stderr), đồng bộ tài liệu; **đo tải 239 và 247 không đạt**, xem `docs/evidence/load-239/` và `load-247/`. A: bug bash giao diện. B: tách `meetings.py`, privacy, reliability, `make`.

### Đợt 4 (giao ngày 2026-11-09: `tasks/2026-11-09/`)

| Member | Việc |
|---|---|
| A | CI chạy thật container web; 401 giữa phiên về đăng nhập; trạng thái rỗng, tải, lỗi; axe |
| B | Profile `POST /meetings`; `API_WORKERS` với phép tính kết nối; tách tiếp `meetings.py`; `make smoke` |
| C | Chẩn đoán 61 s ở 247 client và sửa (giới hạn request đang xử lý); metric quá tải; tài liệu lưu trữ khớp cấu hình; bản đồ bằng chứng `docs/evidence/README.md` |

Kết quả phần C: nguyên nhân là thread và kết nối DB chặn nhau (`docs/evidence/load-247/diagnosis.md`). 247 client: 247/247 upload, 0 lỗi (trước: 91 thành công, 155 lỗi 503). p95 tất cả 3,1 đến 3,4 s với 1 process (**chưa đạt** 2,0 s), 1,8 đến 1,9 s với 4 process, nhưng p95 chỉ-upload 2,2 đến 2,4 s nên **không** ghi là đạt. 40 client: 0,65 s, đạt.

### Đợt 5 (giao ngày 2026-11-10: `tasks/2026-11-10/`, mỗi người 10 commit)

Bắt đầu sau khi #44 (A) và #45 (B) vào `main` ngày 2026-11-10; C review cả hai và gỡ xung đột ở `docker-images.yml`. Đây là đợt tính năng cuối: PR mở trước tối 11-11, ngày 11-12 đóng băng code.

| Member | Việc |
|---|---|
| A | Upload và poll chịu được 503 (`Retry-After`, cùng `Idempotency-Key`); sửa không mất nội dung khi API bận; thời gian chờ hàng đợi của job; E2E qua container web; bàn phím; coverage; clone sạch |
| B | `/metrics` gộp nhiều process; ngân sách kết nối có phần dự trữ; upload ra service; `meetings.py` < 500 dòng có test giữ; smoke dễ đọc khi fail; log có giới hạn; diễn tập runbook; profile vào repo |
| C | Test upload không phụ thuộc ffprobe; CI chạy ffprobe thật; metric thời gian chờ admission; harness tách client/server và chạy nhiều process; đo lại 247, 239, 40; thời gian phản hồi PR; ROADMAP và bản đồ bằng chứng |

### Đợt 6 (giao ngày 2026-11-11: `tasks/2026-11-11/`, mỗi người 5 commit)

Bắt đầu sau khi #47 (A) và #48 (B) vào `main` (`1f9d1ca`). Trước khi merge, C gộp thử cả hai và chạy test: backend 393 passed / 14 skipped, frontend 284/284. Đợt 5 không còn việc chuyển sang. Đây là ngày cuối trước đóng băng code.

| Member | Việc |
|---|---|
| A | Query đọc dữ liệu thử lại theo `Retry-After`, chỉ khi 503 hoặc mất mạng; trang danh sách và chi tiết có trạng thái bận; thông báo bận đọc được bằng trình đọc màn hình; chạy lặp test mới để kiểm flaky |
| B | Metric stage của worker hiện trên `/metrics` của API; gauge theo DB không giữ số cũ; process chết không còn bị cộng; query budget cho đường poll; README backend khớp cấu hình |
| C | Harness hết race keep-alive; harness có số phía server khi chạy nhiều process; đo lại 247, 239, 40 sau #48; bản đồ bằng chứng |

### Đợt 7 (giao ngày 2026-11-12: `tasks/2026-11-12/`, đóng băng code)

Bắt đầu sau khi #50 (A) và #51 (B) vào `main` (`d9c2d50`, CI xanh). Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.

| Member | Việc |
|---|---|
| A | Frontend từ clone sạch; ảnh giao diện tiến độ cho VT-018; bấm chạy lại hai lần không tạo hai job |
| B | Backend từ clone sạch, có và không có Postgres; bằng chứng xóa dữ liệu qua mọi module và log; biên lưu trữ 14 và 28 ngày |
| C | Test do AI sinh cho retry và hàng đợi job, đo bằng mutation, xóa hoặc sửa test yếu (VT-018); số đo cuối của VT-018 |

### Lịch tới hạn nộp (hạn nộp 2026-11-14, người dùng xác nhận ngày 2026-11-09)

| Ngày | Mục tiêu | Ai |
|---|---|---|
| 11-10 | Đợt 4 đã xong: #43, #44, #45 vào `main`. Giao Đợt 5. C đo lại 247 trên `main` (dời lên từ 11-11 vì thay đổi của B đã merge) | A, B, C |
| 11-11 | #47, #48 vào `main` (Đợt 5 xong). Đợt 6: mỗi người 5 commit, mở PR trong ngày; nhóm trưởng merge khi CI xanh | A, B, C |
| 11-12 | **Đóng băng code**: chỉ sửa lỗi. Chạy lại toàn bộ test, `make smoke`, E2E; README chạy được từ clone sạch | A, B, C |
| 11-13 | **Đóng băng bằng chứng**: `docs/evidence/README.md` khớp số liệu cuối; mọi PR đã merge; ghi hash cuối | C |
| 11-14 | Hạn nộp. Không đổi code. Dành cho PDF cá nhân (ngoài repo) | người dùng |

Phần cá nhân của BT1/BT2/BT3 (phân tích, Bước 0 trước khi code, reflection, PDF) do người dùng viết; repo chỉ cung cấp bằng chứng.

## Việc treo

- Đã xong: #33–#39 vào `main`. Nhánh `tainguyen-vt018-tests` (Đợt 2 của C) vào `main` qua PR hôm 2026-11-08.
- Đo tải 247: 1 process **không đạt** ở mọi ngày; 11-16 cho thấy process chạm trần khoảng 1 CPU. 2 process đạt 3/3 (chỉ đo 11-16). 4 process đạt 11-10 (10/12), 11-15 (9/9) và 11-16 (3/3), không đạt 11-11 (0/15); A/B 11-15 cho thấy không do code. Compose vẫn đặt `API_WORKERS: 1`: đổi mặc định là quyết định cấu hình, cần đo lại trên Compose. Chưa biết vì sao ngày 11-11 chậm hơn (khác biệt đã biết: cluster Postgres mới, TCP thay vì Unix socket). Xem mục Tải.
- PR #40 vào `main` ngày 2026-11-08 không có review ghi lại trong PR; #41 và #42 có review (A review #41, C review #42).
- PR #43 (VT-018) vào `main` ngày 2026-11-09 **trước** khi có review; B review sau khi merge, ở `docs/backend/reviews/PR-43-2026-11-09.md` (vào `main` qua #45). Ngày 2026-11-10 nhóm trưởng bỏ yêu cầu review của thành viên khác (xem mục Tham số).
- #44 và #45: C review (approve có ghi chú) rồi merge ngày 2026-11-10. Các điểm làm tiếp của review #45 nằm trong `tasks/2026-11-10/member-b.md`.
- BT3: test AI thô và việc xóa hoặc sửa test yếu đã có (`docs/evidence/vt-018/ai-tests/`, 2026-11-12). Bước 0 (plan AI trước khi code, bác bỏ ≥ 2 điểm) là phần của người dùng. Plan thô của AI cho bộ test này ở `docs/evidence/vt-018/ai-tests/01-plan-raw.md`, commit trước khi có test.
- 40 client 11-12: 1/6 lượt không đạt, hai mức độ trễ, nguyên nhân chưa rõ. Đã loại ffprobe (11-13), fsync khi commit và ghi đĩa (11-15), thứ tự chạy (11-16); thư mục lưu đầy chỉ giải thích khoảng 0,1 s. Mức chậm không tái hiện ở 40 lượt sau đó.
- Từ 11-16 harness tải xóa file audio và artifact của các meeting nó tạo sau mỗi lượt (`--keep-audio` để giữ). Trước đó không dọn, nên thư mục lưu của máy đo lên 22.947 thư mục (2,3 GB); số này giữ nguyên, vì không biết thư mục nào là của harness. `LocalStorage` vẫn cứng thư mục `backend/appdata` (không có biến môi trường).

- SH-01: chưa có bản ghi âm họp thật. AI-12 phần thu thật, AI-14, benchmark trên audio họp phụ thuộc vào đây.
- Quyết định về Claude API với audio họp thật và ngân sách API.
- Đã xong (Đợt 3): `README.md` mục Trạng thái và `structure/architecture.md` không còn ghi backend chưa bắt đầu (kiểm lại 2026-11-10).

### Đợt 8 (giao ngày 2026-11-13: `tasks/2026-11-13/`, đóng băng bằng chứng)

Bắt đầu sau khi #53 (A) vào `main` (`a75853d`, CI xanh 12/12). B push việc 11-12 lên `haquang` nhưng chưa mở PR; C mở #54 thay, review, merge khi CI xanh 15/15 (`f255e01`). Ngày 11-14 nộp bài.

| Member | Việc |
|---|---|
| A | E2E trên `main` có cả #53 và #54; kịch bản demo gắn với ảnh và test của VT-018 |
| B | `GET summary` trả `failed` khi meeting `partial` (lỗi A báo ở #53), test đỏ trước; đọc lại bảng xóa dữ liệu sau khi C sửa |
| C | Test xóa dữ liệu trên Postgres đã migrate (test cũ chạy SQLite); sửa bảng bằng chứng AD-018; chẩn đoán 40 client (ffprobe thật/giả); thời gian phản hồi PR; bản đồ bằng chứng |

### Đợt 9 (giao ngày 2026-11-15: `tasks/2026-11-15/`, sau hạn nộp 11-14, mỗi người 5 commit)

Bắt đầu sau khi #56 (B) và #57 (A) vào `main` (`1e71c89`, `115c905`). C gộp thử cả hai: backend 444 passed / 16 skipped; #56 CI xanh 15/15. Người dùng giao tiếp việc sau hạn nộp. Chỉ sửa lỗi, thêm test và bằng chứng; không thêm tính năng.

| Member | Việc |
|---|---|
| A | Giao diện và MSW theo API sau #56; poll tóm tắt dừng khi `failed`; E2E kiểm API thật trả `failed` cho meeting `partial`; ảnh màn tóm tắt lỗi cho demo |
| B | `GET meeting` trả `summary_status: ready` cho meeting `partial` (`meetings.py:87`); transcript của meeting `ready` có 0 segment trả `pending` (`transcript.py:116`); test log access và log container không giữ canary; giới hạn log ở mọi service |
| C | Test chặn file bằng chứng không phải UTF-8; 40 client: fsync khi commit và ghi audio; 247 client tách CPU máy sinh tải; thời gian phản hồi PR, bản đồ bằng chứng |

Việc chung: A và B comment review PR của nhau trong 18 giờ (không chặn merge), vì 18/23 PR từ 11-06 merge khi chưa có phản hồi của người khác.

### Đợt 10 (giao ngày 2026-11-16: `tasks/2026-11-16/`, sau hạn nộp, mỗi người 5 commit)

Bắt đầu sau khi #60 (A) vào `main` (`544333d`, CI xanh 11/11). #61 (B) chưa merge: A review sau 4,4 giờ, nêu hai điểm. C chạy uvicorn thật và xác nhận access log ghi `?q=<canary>`; đọc code xác nhận smoke Compose báo thành công khi không đọc được log. B sửa trên chính #61.

| Member | Việc |
|---|---|
| A | Log nginx không ghi query string; ô tìm cuộc họp gửi `q` lên API thay vì lọc trang đang xem (`MeetingListPage.tsx:35`), có E2E trên API thật; transcript `ready` không có lời nói hiện đúng câu và không poll |
| B | Trên #61: tắt access log của uvicorn, có test chạy uvicorn thật; smoke Compose lỗi khi không đọc được log, và tìm theo tiêu đề canary; `segment_count`, `speaking_time_sec` luôn bằng 0 ở transcript và meeting detail |
| C | Harness dọn file của meeting nó tạo; CPU của event loop ở 247 client, 1 và 4 process; 40 client thư mục đầy và rỗng, đổi thứ tự; thời gian phản hồi PR, bản đồ bằng chứng |

Thứ tự merge: #61 trước PR của A, vì A cho giao diện gửi tiêu đề tìm kiếm qua `?q=`.

### Đợt 11 (giao ngày 2026-11-17: `tasks/2026-11-17/`, sau hạn nộp, mỗi người 5 commit)

Bắt đầu sau khi #61 (B, `8fcf72e`, CI 18/18) và #64 (A, `1dc6b5c`, CI 15/15) vào `main`. C review diff cả hai: #61 sửa đúng hai điểm của A (`--no-access-log` có test uvicorn thật; smoke lỗi khi không đọc được log) và số liệu người nói; #64 có test cho debounce, `q` lên API, transcript rỗng. Khi đọc diff C thấy một lỗi mới do #64 làm lộ: `meetings.py:145` ghép `q` vào `ilike` mà không escape `%`, `_`.

| Member | Việc |
|---|---|
| A | E2E trên API thật: `%` và `_` trong ô tìm là ký tự thường; tìm kiếm lỗi mạng giữ từ khóa và có thử lại; phản hồi cũ không ghi đè phản hồi mới; đổi bộ lọc trạng thái về trang 1 |
| B | Escape `%`, `_`, `\` trong `q` và giới hạn độ dài; test hợp đồng ghi vào `backend/appdata` thật (C đếm 15 thư mục, +1 mỗi lần chạy backend); `q` + `status` + phân trang; số liệu người nói sau khi đổi người nói |
| C | Harness đếm log của API dưới tải; 247 client (1, 2, 4 process) và 40 client trên `main` sau #61, #64; bản đồ bằng chứng, ROADMAP, thời gian phản hồi PR |

Thứ tự merge: PR của B trước PR của A, vì việc 1 của A cần việc 1 của B.

**Kết quả:** #67 (B, `efbbed9`) rồi #66 (A, `006fd8c`). C chạy lại #67 trên PostgreSQL 16: 500 passed, 0 skipped. C chạy E2E wildcard của A trên #66 gộp với `main`: 3/3 passed. B review #66 sau 31,4 giờ; A không review #67. Hai điểm từ review #67 chuyển sang Đợt 12: guard của B xóa thư mục trong `backend/appdata/audio` thật; B ghi 24 skipped thay vì chạy trên Postgres.

### Đợt 12 (giao ngày 2026-11-19: `tasks/2026-11-19/`, sau hạn nộp, mỗi người 5 commit)

Bắt đầu sau khi #67 và #66 vào `main` (`006fd8c`). Lỗi mới C thấy khi soạn việc: ô tìm không có `maxLength`, nên từ #67 dán quá 200 ký tự thì API trả 422; bộ lọc trạng thái không có mục nào nhưng màn hình báo "Chưa có cuộc họp"; `LocalStorage()` cố định `backend/appdata`; `GET /meetings` chạy 1 truy vấn `Job` cho mỗi cuộc họp trong trang (N+1, chưa giao, để đợt sau).

| Member | Việc |
|---|---|
| A | E2E wildcard xanh trên `main` và tick việc 1 ngày 11-17; ô tìm dừng ở 200 ký tự; trang hiện tại rỗng mà `total > 0` thì về trang cuối; trạng thái rỗng theo bộ lọc |
| B | Guard thư mục lưu chỉ báo lỗi, không xóa; `STORAGE_DIR` trong `Settings`, test dùng thư mục tạm; tìm không phân biệt hoa thường với chữ tiếng Việt trên Postgres; trang quá cuối, `page=0`, `page_size=101` |
| C | Harness có `--search` (tìm `%`, `_`, `100%`, tiêu đề dưới tải, đếm kết quả sai); 247 client (1, 2, 4 process) và 40 client có tìm kiếm trên `main` sau #67, #66, kèm lượt đối chứng trước #67; bản đồ bằng chứng, ROADMAP, thời gian phản hồi PR |

Hai PR của A và B không phụ thuộc nhau; việc 3 của A dựa vào hành vi API mà việc 4 của B khóa bằng test.

**Kết quả:** #69 (A, `9a87355`) và #70 (B, `5c29101`), CI 12/12 và 15/15. C chạy lại #70 trên PostgreSQL 16: 515 passed, 0 skipped, `backend/appdata` thật không đổi. B approve #69 sau 8,0 giờ. A review #70 sau 63,3 giờ, quá hạn, nhưng finding P2 đúng: preflight socket `AF_INET` mới trong `conftest.py` trả False với URL `[::1]`, và C tái hiện được. Điểm này chỉ nằm ở phần chuẩn bị test, nên C merge và giao sửa cho B (Đợt 13, việc 1).

### Đợt 13 (giao ngày 2026-11-23: `tasks/2026-11-23/`, sau hạn nộp, mỗi người 5 commit)

Bắt đầu sau khi #69 và #70 vào `main` (`5c29101`). Lỗi mới C thấy khi soạn việc:
- Nút "Xóa bộ lọc" vẫn gửi từ khóa cũ thêm 300 ms.
- Lúc đang tải hoặc lỗi, tiêu đề ghi "0 cuộc họp".
- Sang trang thì thanh phân trang biến mất trong lúc tải (danh sách không giữ dữ liệu cũ).
- Worker dự phòng ghi artifact vào `./appdata` tương đối (`runner.py` dòng 273).
- N+1 ở `GET /meetings`, để từ 11-19, giờ giao B.

| Member | Việc |
|---|---|
| A | "Xóa bộ lọc" bỏ từ khóa cũ ngay; ẩn số đếm khi đang tải hoặc lỗi; thanh phân trang giữ nguyên khi sang trang; E2E trên API thật cho trang 2 bị xóa hết và bộ lọc trạng thái rỗng |
| B | Preflight Postgres nhận IPv6; N+1 ở `GET /meetings` (test ngân sách truy vấn rồi sửa); xóa cuộc họp theo đúng `STORAGE_DIR`; worker dự phòng theo `STORAGE_DIR` |
| C | Harness ghi vào thư mục lưu trống mỗi lượt qua `STORAGE_DIR`, xóa thư mục tạm; 247 client trên 2 process, có và không có tìm kiếm xen kẽ; 40 client, thư mục trống và thật xen kẽ; bản đồ bằng chứng, ROADMAP, thời gian phản hồi PR |

Hai PR không phụ thuộc nhau. Sau khi B sửa N+1, C đo lại 247 client có tìm kiếm.

**Kết quả (Đợt 13):** C và A đã merge, B thì chưa.
- #71 (C) merge `6d5f94d`, kèm commit sửa `1eed9b8` do **B** viết và đẩy lên nhánh `tainguyen`, vì CI đỏ ở `test_evidence_map_links`: chuỗi `backend/appdata` trong backtick bị đọc thành đường dẫn file, mà thư mục này có trên máy đo nhưng không có trên CI.
- #72 (A) merge `b35e06f`. C chạy lại E2E trang rỗng trên API thật: 3/3 passed.
- B chưa mở PR, nhánh `haquang` chưa có commit mới. Việc của B chuyển sang Đợt 14.

### Đợt 14 (giao ngày 2026-11-24: `tasks/2026-11-24/`, sau hạn nộp, mỗi người 5 commit)

Bắt đầu từ `main` `b35e06f`. Lỗi mới C thấy khi soạn việc:
- **Đổi tên cuộc họp thật không lưu lên API:** `RemoteMeetingContent` chỉ đổi state, và `client.ts` không có `PATCH /meetings/{id}`. Đây là lỗi mất dữ liệu đã sửa (AD-018).
- **Bốn trường trả 500 trên PostgreSQL khi quá giới hạn.** C viết `backend/tests/integration/test_field_limits_postgres.py`, có `xfail` strict cho 4 ca này:
  - `POST /meetings`: `title` 201 ký tự, `meeting_date` sai định dạng, `Idempotency-Key` 101 ký tự.
  - `POST /action-items`: `due_date` sai định dạng.
- **Ô sửa transcript không chặn 5000 ký tự.**
- **Dòng của trang cũ hiện như trang mới trong lúc tải** (review #72).

| Member | Việc |
|---|---|
| A | Đổi tên lưu qua `PATCH /meetings/{id}`, quay lại tên cũ khi 409; E2E đổi tên trên API thật; ô sửa transcript dừng ở 5000 ký tự; đánh dấu dòng của trang cũ đang tải |
| B | Chuyển từ 11-23: preflight IPv6, N+1 ở `GET /meetings`, worker dự phòng theo `STORAGE_DIR`. Mới: bốn trường trả 500 trên Postgres, sửa xong thì bỏ `xfail`. Việc test xóa cuộc họp theo `STORAGE_DIR` để đợt sau |
| C | Test giới hạn mọi trường chữ trên PostgreSQL; 247 client 1 và 4 process với thư mục lưu trống; 40 client; bản đồ bằng chứng (thêm dòng "Sửa đổi được"), ROADMAP, thời gian phản hồi PR |

**Kết quả (Đợt 14):**
- #74 (A, `46feb59`): đổi tên cuộc họp lưu qua `PATCH` và có E2E. B review sau 12,4 giờ.
- #75 (B, `70b527a`): IPv6, N+1, bốn trường 500, worker dự phòng; 6 commit, có thêm refactor không được giao. A review sau 0,5 giờ, finding P2 đúng: khi `created_at` trùng, danh sách và chi tiết chọn hai job mới nhất khác nhau (C tái hiện).
- C gộp hai PR với `main` rồi chạy trên PostgreSQL 16: 536 passed, 1 skipped (test cần Postgres nghe IPv6).

### Đợt 15 (giao ngày 2026-11-25: `tasks/2026-11-25/`, sau hạn nộp, mỗi người 5 commit)

Bắt đầu từ `main` `70b527a`. Lỗi mới C thấy khi soạn việc:
- `audio.size_bytes` luôn là 0.
- `PUT /summary` nhận `evidence_segment_ids` không thuộc cuộc họp (C bắt bằng test, `xfail` strict).
- Trên cuộc họp thật, tóm tắt không dừng ở 50 ý, và ô công việc, ô tổng quan không có giới hạn độ dài.
- Bản sửa N+1 không làm 247 client nhanh hơn.

| Member | Việc |
|---|---|
| A | Tóm tắt dừng ở 50 ý chính và 50 quyết định; giới hạn độ dài của công việc và tổng quan trên cuộc họp thật; E2E sửa tóm tắt trên API thật; ngày họp bị API từ chối |
| B | Thứ tự job mới nhất dùng chung (P2 của A); `size_bytes` thật; xóa file theo `STORAGE_DIR` (chuyển từ 11-23); dẫn chứng của tóm tắt phải thuộc cuộc họp. Đúng 5 commit |
| C | Test giới hạn cho các endpoint ghi còn lại; 247 client trước/sau N+1 xen kẽ, kèm đo riêng `GET /meetings`; 40 client; bản đồ bằng chứng, ROADMAP, thời gian phản hồi PR |
