# 2026-11-06 · Member C: pipeline, evaluation, nhóm trưởng

- **Người làm:** C (`@TAINGUYENVAN0507`).
- **Số commit:** 5. Commit 1–3 trên nhánh mới `tainguyen-vt018`; commit 4–5 trên `tainguyen`.
- **Mục tiêu:**
  - sửa lỗi retry tạo bản ghi trùng và tiến độ tụt lùi, theo đúng thứ tự test đỏ, patch, test xanh;
  - khóa adapter boundary bằng test;
  - pipeline ghi sự kiện có cấu trúc để truy nguyên nhân.

Kế hoạch các đợt sau và bảng yêu cầu: [`tasks/ROADMAP.md`](../ROADMAP.md).

## Đã kiểm chứng trước khi giao

Chạy trên SQLite in-memory với fake pipeline, code tại `53f753b`, ngày 2026-11-06:

| Kịch bản | Kết quả hiện tại | Kỳ vọng |
|---|---|---|
| Job thứ 2 của cùng meeting (`from_stage=asr`, chưa có chỉnh sửa) | Segment từ 6 thành 12, `idx` 0, 1, 2 lặp | Vẫn 6 |
| Job mới `from_stage=asr`, progress khởi tạo 0.333 (`meetings.py:2220`) | Lần ghi đầu là 0.05 | Không giảm |
| `GET /jobs/{id}` | `started_at`, `finished_at` luôn `null` (`jobs.py:78`, `meetings.py:453`, `meetings.py:2087`) | Giá trị thật |

Nguyên nhân: guard idempotent của `persist_transcript` theo `(job_id, stage)` chỉ đúng khi retry cùng job. Job mới có id mới nên lọt qua, và `segments` không có unique `(meeting_id, idx)`.

Lệnh kiểm tra từ gốc repo. Commit 1–3 chạy phần `backend`; commit 4–5 chạy cả hai:

```bash
(cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest)
(cd pipeline && uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not model" && uv run python -m meeting_pipeline export-contracts --check)
```

Test của `persister` và `worker` dùng SQLite nên chạy được ở máy này. Test cần Postgres sẽ skip ở local và chỉ có kết quả trên CI. Muốn chạy Postgres không cần Docker: máy có sẵn `/usr/lib/postgresql/16/bin/{initdb,pg_ctl}`, chưa thử.

## Bước 0 (không tính vào số commit)

Thứ tự này là yêu cầu của VT-018, không đổi được.

```bash
git fetch origin
git switch -c tainguyen-vt018 origin/main   # không đặt tainguyen/vt018 được vì đã có nhánh tainguyen
git rev-parse HEAD                          # baseline, ghi vào dòng dưới
```

- **Baseline:** `adacad9`
- [ ] Dùng coding agent lập implementation plan **trước khi code**. Lưu prompt, assumptions, danh sách file dự định đổi và output thô vào `reports/bt3/` (cá nhân, không commit).
- [ ] Review plan bằng repo thật. Ghi ít nhất 2 điểm sửa hoặc bác bỏ kèm file và dòng làm bằng chứng.
- [ ] Cho AI sinh test cases. Lưu bản thô, sau đó xóa hoặc sửa ít nhất 2 test yếu hoặc trùng và ghi lý do. Việc này là yêu cầu bắt buộc của đề, nên phải có bản thô để đối chiếu.

## 5 commit

### 1. [x] Test đỏ: rerun và tiến độ (BE-17, VT-018) · nhánh `tainguyen-vt018`

- **Việc:** thêm `backend/tests/unit/test_vt018_rerun_progress.py`:
  - `test_vt018_second_job_keeps_one_segment_set`: job 2 của cùng meeting không làm tăng số segment, không lặp `idx`;
  - `test_vt018_progress_never_decreases_on_rerun`: chuỗi progress ghi vào DB không giảm;
  - `test_vt018_progress_never_decreases_after_transient_retry`: như trên với `FAKE_SCENARIO=transient_once`, lượt 2 đi qua checkpoint;
  - `test_vt018_job_out_has_real_timestamps`: `GET /jobs/{id}` có `started_at`, `finished_at` đúng;
  - `test_vt018_merge_rerun_with_user_edits_is_rejected`: `from_stage=merge` khi đã có chỉnh sửa trả 409 `HAS_USER_EDITS`. Hiện `merge` không nằm trong guard ở `meetings.py:2181`.
- Gắn `@pytest.mark.xfail(strict=True, reason=...)` để CI vẫn xanh theo `rules/git-workflow.md`. Lấy evidence đỏ bằng `--runxfail`.
- **Xong khi:** đọc log và xác nhận từng test fail vì assert đúng lý do, không phải lỗi fixture hay import:
  ```bash
  mkdir -p docs/evidence/vt-018
  (cd backend && uv run pytest --runxfail tests/unit/test_vt018_rerun_progress.py) 2>&1 | tee docs/evidence/vt-018/01-red.log
  ```
- **Message:** `test(worker): reproduce duplicate rows and regressing progress on rerun (BE-17, VT-018)`
- **Hash:** `0722b05`

### 2. [x] Patch: job mới thay transcript cũ, có unique ở DB (BE-17, VT-018) · nhánh `tainguyen-vt018`

- **Việc:**
  - `persist_transcript`: job mới của meeting đã có segment thì xóa bộ cũ và ghi bộ mới trong cùng transaction. Speaker không còn trong transcript mới cũng xóa.
  - Migration `0006`: unique `(meeting_id, idx)` trên `segments`, có downgrade. Upgrade phải chạy được khi DB đã có dòng trùng do lỗi này: giữ bộ mới nhất theo `created_at`.
  - Thêm `merge` vào guard `HAS_USER_EDITS` (`meetings.py:2181`). Nếu không, bản fix này sẽ xóa mất chỉnh sửa của người dùng.
- **Cần tự kiểm tra thêm:**
  - Summary cũ giữ `evidence_segment_ids` trỏ tới segment vừa xóa. Nếu job mới lỗi ở `summarize` thì evidence bị treo: phải có test và cách xử lý.
  - `persist_summary` giữ action item đã sửa (`version > 1`) rồi thêm item AI mới, nên có thể trùng về nội dung. Quyết định có sửa không, ghi vào PR.
  - Workdir theo từng job (`artifacts/{meeting}/{job}`), nên job mới `from_stage=asr` thực ra chạy lại từ `preprocess`. Không cần sửa hôm nay, nhưng khởi tạo progress phải đúng với việc này.
- **Xong khi:** bỏ `xfail` của 2 test tương ứng; test xanh; log ở `docs/evidence/vt-018/02-green-rerun.log`; đã đọc lại toàn bộ diff.
- **Message:** `fix(worker): a new job replaces the previous transcript instead of duplicating it (BE-17, VT-018)`
- **Hash:** `abe2205`

### 3. [x] Patch: tiến độ không tụt, thời gian job là thật (BE-17, VT-018) · nhánh `tainguyen-vt018`

- **Việc:**
  - `handle_progress` (`runner.py:305`) không ghi giá trị nhỏ hơn progress hiện tại.
  - Migration `0007`: cột `started_at`, `finished_at` của `jobs`, có downgrade. `started_at` đặt ở lần claim đầu và giữ qua retry; `finished_at` đặt khi vào trạng thái kết thúc.
  - Sửa cả 3 chỗ trả `None`: `jobs.py:78`, `meetings.py:453`, `meetings.py:2087`. Không đổi schema, nên `contracts/openapi.json` phải giữ nguyên: kiểm bằng test drift.
- **Xong khi:** bỏ `xfail` còn lại; toàn bộ `uv run pytest` xanh; log ở `docs/evidence/vt-018/03-green-progress.log`.
- **Message:** `fix(worker): progress never goes backwards and job timestamps are real (BE-17, VT-018)`
- **Hash:** `5112afb`

### 4. [x] Test khóa adapter boundary (AI-17, AD-018) · nhánh `tainguyen`

Hiện ranh giới chỉ ghi trong `structure/architecture.md`, không có gì chặn. `models.py:109` còn import `faster_whisper.utils._MODELS`, là API private của SDK, nằm ngoài `engines/`.

- **Việc:**
  - Test duyệt AST, không thêm dependency, bắt được cả import trong hàm:
    - pipeline: `anthropic` chỉ trong `llm/anthropic.py`; `faster_whisper` chỉ trong `engines/whisper.py`; `pyannote`, `torch` chỉ trong `engines/pyannote.py`; `huggingface_hub` chỉ trong `models.py`;
    - backend: `app/api/` không import `meeting_pipeline`; `app/worker/` chỉ import `runner`, `schemas`, `errors`.
  - Chuyển `asr_repo` sang `engines/whisper.py` để bỏ vi phạm ở `models.py:109`.
  - Có test âm: đưa source vi phạm vào hàm kiểm tra thì phải báo lỗi và nêu tên file, dòng.
  - Viết `docs/pipeline/AI-17.md`: bảng dịch vụ, adapter, bản fake, dữ liệu gửi đi, test bảo vệ.
- **Xong khi:** thêm thử `import anthropic` vào `stages/` thì test đỏ, gỡ ra thì xanh; ghi kết quả vào `docs/pipeline/AI-17.md`.
- **Message:** `test(pipeline,backend): adapter boundary enforced by an import check (AI-17, AD-018)`
- **Hash:** `09364f2`

### 5. [x] Pipeline ghi sự kiện có cấu trúc (AI-18, RE-018) · nhánh `tainguyen`

- **Việc:**
  - `runner.py` ghi `stage_started`, `stage_finished`, `stage_failed`, `stage_skipped`, `stage_fallback` qua `log.info(..., extra=...)` với các field chung ở `tasks/ROADMAP.md`, mục Field log.
  - Không ghi text transcript, tiêu đề, đường dẫn tuyệt đối.
  - Ghi field vào `pipeline/README.md`.
- **Xong khi:**
  - test với fake pipeline: `ok` có đủ start và finish cho 6 stage kèm `duration_sec`; `permanent` có `stage_failed` kèm `error_code`; `diarize_fail` có `stage_fallback`;
  - canary `CANARY_TRANSCRIPT_7f3a` không có trong log (PRIV-10).
- **Message:** `feat(pipeline): structured stage events with job id, duration and error code (AI-18, RE-018)`
- **Hash:** `72660e6`

## Việc của nhóm trưởng (không phải commit)

- [ ] Review và merge PR của A và B (không có file nào của họ đụng phần commit 1–3 nếu họ làm đúng mục "Tránh đụng").
- [ ] Mở PR `tainguyen-vt018` → `main` sau commit 3, nhờ B review. **Không merge khi B chưa review**, kể cả khi CI xanh: đây là yêu cầu của VT-018.
- [ ] Giữ `meetings.py` tại `53f753b` làm mốc phân tích cho AD-018. B sẽ đổi file này, nên mọi trích dẫn phải ghi hash.
- [ ] SH-01: tổ chức buổi ghi âm pilot (vẫn chưa có). AI-12 phần thu thật, AI-14 và benchmark trên audio họp đang chờ dữ liệu này.
- [ ] Quyết định có dùng Claude API với audio họp thật không (cần consent theo phiếu) và ngân sách API.

## Kết quả (ghi ngày 2026-11-07)

- Commit 1–3 nằm ở PR #35 (`tainguyen-vt018`), **chưa merge**: chờ B review theo yêu cầu VT-018. CI xanh.
- Commit 4–5 trên `tainguyen`.
- Bước 0 (plan AI, test AI thô, bác bỏ ≥ 2 điểm, xóa/sửa ≥ 2 test yếu) là việc của nhóm trưởng, nằm ở `reports/bt3/`, **chưa làm**: phải có trước khi nộp BT3.
- Test local có 6 lỗi `AUDIO_INVALID` do máy có `ffprobe` thật; CI xanh. Không liên quan tới thay đổi này.

## Cuối ngày

- [ ] Tick các ô ở trên và ghi hash, trên nhánh `tainguyen`.
- [ ] Cập nhật `tasks/ROADMAP.md`.
- [ ] Bài PDF cá nhân không commit vào repo. Việc phải làm cho từng bài nằm ở `reports/016-*`.
