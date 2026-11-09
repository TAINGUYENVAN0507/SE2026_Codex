# Kế hoạch còn lại

> Cập nhật 2026-11-08. Trạng thái bên dưới đọc từ code tại `53f753b` (2026-11-06); các dòng ✓ mới thêm ghi PR kèm theo. Nhóm trưởng cập nhật file này mỗi khi phân công.

## Tiếp tục vào ngày sau

1. Đọc `tasks/<ngày gần nhất>/member-*.md`: ô nào chưa tick thì ghi "chuyển từ <ngày>" sang file mới.
2. Lấy việc của đợt kế tiếp ở mục [Lịch](#lịch), tạo `tasks/<ngày>/member-{a,b,c}.md`, mỗi người 5 commit.
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

Quy ước của nhóm, để hai con số lưu trữ của RE-018 và AD-018 không mâu thuẫn:

| Biến | Mặc định | Áp dụng cho |
|---|---|---|
| `AUDIO_RETENTION_DAYS` | 14 | Audio và artifact của job (artifact chứa transcript dạng JSON) |
| `OPERATIONAL_RETENTION_DAYS` | 28 | `idempotency_keys`, log. Không chứa nội dung cuộc họp |

Transcript trong DB giữ tới khi người dùng xóa. Hai giá trị đặt qua biến môi trường nên đổi được, không sửa code.

Không ghi hệ thống chịu được 239 hay 247 người dùng khi chưa đo. Mức đo bắt buộc là 40 (đợt 2); đo ở 239 và 247 ở đợt 3.

**Phản hồi:** trong các đợt này, PR được review trong 18 giờ kể từ lúc mở (đáp ứng cả 18 và 20 giờ).

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

Hiện trạng đọc từ code tại `53f753b`. ✓ đã có · ◐ một phần · ✗ chưa có. Lỗi ghi "đã tái hiện" đã chạy thử ngày 2026-11-06.

### RE-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Tóm tắt dẫn về đúng đoạn audio | ◐ Có ở key point; action item chưa có (`RemoteTasks.tsx`) | FE-18 | A | 1 |
| File export kiểm chứng được | ✗ TXT và MD không in evidence (`serializers.py:125`); router còn là stub (`meetings.py:2376`) | FE-18, BE-05 | A, B | 1 |
| Log truy được theo job | ✗ `setup_logging()` không được gọi ở đâu; worker dùng `basicConfig` (`runner.py:573`) | BE-19, AI-18 | B, C | 1 |
| Metric có số đo | ✗ Không có `/metrics` | BE-19 | B | 1 |
| Thời lượng từng stage trong metric | ✗ Worker bỏ `outcome.timings` (`runner.py:381`) | BE-19 | B | 2 |
| Runbook truy nguyên nhân, có thời gian đo thật | ✗ | BE-19 | B | 1 |
| Lưu 14 ngày chạy thật | ✗ Hard-code 30 ngày (`meetings.py:284`), không có gì xóa | BE-14 | B | 1 |
| Mỗi PR có review và test evidence | ◐ Có template; PR của nhóm trưởng mới tự review | PR VT-018 do B review | B, C | 1 |

### AD-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Xóa khỏi mọi nơi lưu | ◐ Đã tái hiện: `idempotency_keys` còn tiêu đề sau khi xóa | BE-18 | B | 1 |
| Xóa được cả tài khoản | ✗ Không có endpoint | BE-18 | B, A | 2 |
| Log không giữ dữ liệu cá nhân | ◐ Cần test canary trên cả 3 tầng | BE-18, BE-19, AI-18 | B, C | 1 |
| Adapter cho bên thứ ba | ✓ `engines/`, `llm/` có interface và bản fake | | C | |
| Có cơ chế cưỡng chế boundary | ✓ Test AST, `docs/pipeline/AI-17.md` | AI-17 | C | 1 |
| Tách controller quá lớn | ✗ `meetings.py` 2412 dòng, 18 route, `serialize_job` lặp với `jobs.py` | Tách từng phần, không đổi hành vi | B | 2, 3 |
| ADR | ◐ Mới có `0001-asr.md` | `docs/adr/0002-*` | C | 3 |

### VT-018

| Yêu cầu | Hiện trạng | Việc | Owner | Đợt |
|---|---|---|---|---|
| Job chạy nền, poll trạng thái | ✓ `POST /meetings`, `GET /jobs/{id}`, poll 2 s | | | |
| Retry không tạo bản ghi trùng | ✓ PR #35 (chờ B review) | BE-17 | C | 1 |
| Tiến độ không tụt | ✓ PR #35 | BE-17 | C | 1 |
| Có thời gian bắt đầu và kết thúc | ✓ PR #35 | BE-17 | C | 1 |
| Giao diện hiện tiến độ | ✓ PR #34 | FE-20 | A | 1 |
| Test pairwise | ✓ `docs/evidence/vt-018/pairwise.md` | Đợt 2, commit 1 | C | 2 |
| Mutation `>` thành `>=` có test bắt được | ✓ `mutation.md` | Đợt 2, commit 2–3 | C | 2 |
| Coverage, flaky | ✓ `docs/evidence/vt-018/README.md` | Đợt 2, commit 5 | C | 2 |
| Tải 40 đồng thời, p95 ≤ 1.5 s | ✓ p95 0,67 s rồi 0,86 s, 0 lỗi (hai lần đo riêng, pipeline fake) | AI-19 | C | 2 |
| README chạy test của bài | ✓ | Đợt 2, commit 5 | C | 2 |

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

## Việc treo

- Đã xong: #33–#39 vào `main`. Nhánh `tainguyen-vt018-tests` (Đợt 2 của C) vào `main` qua PR hôm 2026-11-08.
- Đo tải 247: chưa đạt p95 ≤ 2,0 s ở cấu hình mặc định; B profile `POST /meetings` (xem `docs/evidence/load-247/after/README.md`).
- PR #40 vào `main` ngày 2026-11-08 không có review ghi lại trong PR; #41 và #42 có review (A review #41, C review #42).
- BT3 Bước 0 (plan AI, test AI thô) chưa làm.

- SH-01: chưa có bản ghi âm họp thật. AI-12 phần thu thật, AI-14, benchmark trên audio họp phụ thuộc vào đây.
- Quyết định về Claude API với audio họp thật và ngân sách API.
- `README.md` mục Trạng thái và `structure/architecture.md` đã lỗi thời (ghi backend chưa bắt đầu). Sửa ở đợt 3 cùng phần cài đặt bằng Compose.
