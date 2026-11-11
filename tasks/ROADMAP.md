# Kế hoạch còn lại

> Cập nhật 2026-11-10. Trạng thái yêu cầu đọc từ `main` tại `fc7d80f`. Nhóm trưởng cập nhật file này mỗi khi phân công.

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

Hiện trạng đọc từ `main` tại `fc7d80f` (sau #44, #45) ngày 2026-11-10, cộng PR #46 của C khi ghi rõ. ✓ đã có · ◐ một phần · ✗ chưa có. Số đo tải: một máy, pipeline fake; chi tiết và giới hạn ở [`docs/evidence/README.md`](../docs/evidence/README.md). Bảng theo code ngày 11-06 (`53f753b`) đã thay bằng bảng này; lịch sử xem git.

### RE-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Tóm tắt dẫn về đúng đoạn audio | ✓ Key point, quyết định và action item đều có link evidence (`EvidenceLinks.tsx`, `RemoteTasks.tsx`) | FE-18 | A | 1 |
| File export kiểm chứng được | ✓ TXT, MD, JSON in evidence (`backend/app/services/export/serializers.py`); E2E `frontend/e2e/flows/export-evidence.spec.ts` | FE-18, BE-05 | A, B | 1 |
| Log truy được theo job | ✓ `setup_logging()` ở API và worker; `backend/tests/api/test_observability.py` | BE-19, AI-18 | B, C | 1 |
| Metric có số đo | ✓ `/metrics`; quá tải và thời gian chờ admission; bucket có mốc 1,5 và 2,0 s (#46) | BE-19 | B, C | 1, 4, 5 |
| Thời lượng từng stage trong metric | ◐ Worker ghi `pipeline_stage_duration_seconds` trong process riêng; `/metrics` của API chưa đọc được (C phát hiện khi review #48, 2026-11-11) | BE-19 | B | 2, 6 |
| Metric đúng khi chạy nhiều process API | ✓ `PROMETHEUS_MULTIPROC_DIR`, `MultiProcessCollector`, `livesum` gộp đủ mọi process API | BE-19 | B | 5 |
| Runbook truy nguyên nhân, có thời gian đo thật | ✓ Diễn tập 2 sự cố trên Compose đo thời gian thật tại `docs/backend/runbook-drill-2026-11-10.md`, bổ sung runbook `docs/backend/BE-19.md` | BE-19 | B | 5 |
| Lưu 14 ngày chạy thật | ✓ Worker gọi `run_retention_cleanup`; `backend/tests/api/test_retention.py`; test giữ tài liệu khớp cấu hình | BE-14 | B, C | 1, 4 |
| 239 người dùng đồng thời | Xem bảng tải bên dưới | AI-19 | C | 3–5 |
| Phản hồi change request trong 20 giờ | ◐ `docs/evidence/pr-response-times.md`: từ 11-06, 4/15 PR có phản hồi của người khác, 3/4 trong 20 giờ; 10 PR merge khi chưa có phản hồi | | A, B, C | |

### AD-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Xóa khỏi mọi nơi lưu | ✓ `backend/app/services/erasure/`; `test_delete_meeting.py`; canary: `idempotency_keys` không còn tiêu đề | BE-18 | B | 1 |
| Xóa được cả tài khoản | ✓ `DELETE /auth/me` và giao diện xóa tài khoản (#42) | BE-18 | B, A | 2 |
| Log không giữ dữ liệu cá nhân | ✓ Canary ở API, worker (`backend/tests/privacy/`) và pipeline (tìm ra và sửa rò stderr) | BE-18, BE-19, AI-18 | B, C | 1, 3 |
| Adapter cho bên thứ ba | ✓ `engines/`, `llm/` có interface và bản fake | | C | |
| Có cơ chế cưỡng chế boundary | ✓ Test AST, `docs/pipeline/AI-17.md` | AI-17 | C | 1 |
| Tách controller quá lớn | ✓ 100% controller trong `app/api/v1/` $\le 500$ dòng (`meetings.py` 455 dòng, `action_items.py` 452 dòng); upload tách sang service; test kiến trúc `test_controller_limits.py` giữ chốt | BE-12 | B | 2–5 |
| ADR | ✓ `docs/adr/0001-asr.md`, `0002-adapter-boundary-and-erasure.md`, `0003-controller-size-limit-and-layer-boundary.md` | | C, B | 3, 5 |
| 247 đồng thời, p95 ≤ 2,0 s | Xem bảng tải bên dưới | AI-19, BE-12 | B, C | 3–5 |
| Lưu dữ liệu vận hành 28 ngày | ✓ `OPERATIONAL_RETENTION_DAYS=28`, `backend/tests/api/test_retention.py` | BE-14 | B | 1 |
| Phản hồi trong 18 giờ | ◐ Như dòng 20 giờ ở RE-018: 3/4 PR có phản hồi là trong 18 giờ; #44 phản hồi sau 22,0 giờ | | A, B, C | |

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
| Coverage, flaky | ✓ `docs/evidence/vt-018/README.md`; #46: 5 test upload từng đỏ trên máy có ffprobe, xanh trên CI, nay ra cùng kết quả ở mọi máy | | C | 2, 5 |
| Tải 40 đồng thời, p95 ≤ 1.5 s | Xem bảng tải bên dưới | AI-19 | C | 2–5 |
| README chạy test của bài | ✓ `docs/evidence/vt-018/README.md` | | C | 2 |

### Tải (cập nhật sau mỗi lần đo)

Đo ngày 2026-11-10 trên `main` sau #44, #45 (cộng metric của #46), một máy 12 CPU, pipeline fake, tải dạng barrier. Chi tiết: `docs/evidence/load-247/after-2026-11-10/README.md`, `docs/evidence/load-239/after-2026-11-10/README.md`, `docs/evidence/vt-018/load-40-2026-11-10/README.md`.

| Mốc | Cấu hình | Kết quả | Trạng thái |
|---|---|---|---|
| VT-018: 40 đồng thời, p95 ≤ 1,5 s | 1 process API | p95 upload 0,36 đến 0,41 s, 3/3 lượt, 0 lỗi | ✓ |
| RE-018: 239 đồng thời (không có mục tiêu độ trễ) | 1 process API | 239/239 upload, 0 lỗi, 4 lượt; p95 upload 2,09 đến 2,37 s | ✓ chịu được |
| AD-018: 247 đồng thời, p95 ≤ 2,0 s | 1 process API (mặc định) | p95 upload 2,25 đến 3,75 s, 14/14 lượt trên mốc | ✗ |
| AD-018: 247 đồng thời, p95 ≤ 2,0 s | 4 process API, `API_MAX_INFLIGHT=20` | p95 upload ≤ 2,0 s ở 10/12 lượt (1,08 đến 2,18 s); sát mốc khi máy bận | ◐ không ghi là đạt chắc chắn |

Ở 247 client có 6 lỗi `RemoteProtocolError` trên 6.669 upload. Nguyên nhân là harness: kết nối rảnh đúng 5 s, bằng timeout keep-alive của uvicorn; đường thật qua nginx không dùng lại kết nối. Thay đổi của B ở #45 giảm p95 khoảng 0,15 s (chạy xen kẽ trước và sau trong cùng điều kiện).

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
- Đo tải 247 (2026-11-10): cấu hình mặc định 1 process **không đạt** p95 ≤ 2,0 s; 4 process đạt ở 10/12 lượt, sát mốc. Muốn chắc hơn thì phải giảm thời gian xử lý mỗi upload (B có profile, chưa có file trong repo) hoặc đo trên máy không chạy chung trình soạn thảo. Xem mục Tải.
- PR #40 vào `main` ngày 2026-11-08 không có review ghi lại trong PR; #41 và #42 có review (A review #41, C review #42).
- PR #43 (VT-018) vào `main` ngày 2026-11-09 **trước** khi có review; B review sau khi merge, ở `docs/backend/reviews/PR-43-2026-11-09.md` (vào `main` qua #45). Ngày 2026-11-10 nhóm trưởng bỏ yêu cầu review của thành viên khác (xem mục Tham số).
- #44 và #45: C review (approve có ghi chú) rồi merge ngày 2026-11-10. Các điểm làm tiếp của review #45 nằm trong `tasks/2026-11-10/member-b.md`.
- BT3 Bước 0 (plan AI, test AI thô) chưa làm.

- SH-01: chưa có bản ghi âm họp thật. AI-12 phần thu thật, AI-14, benchmark trên audio họp phụ thuộc vào đây.
- Quyết định về Claude API với audio họp thật và ngân sách API.
- Đã xong (Đợt 3): `README.md` mục Trạng thái và `structure/architecture.md` không còn ghi backend chưa bắt đầu (kiểm lại 2026-11-10).
