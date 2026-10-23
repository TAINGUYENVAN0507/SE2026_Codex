# meeting_pipeline

Pipeline AI/Speech của *Vietnamese Meeting Minutes Assistant*. Owner: member C. Reviewer: member B.

Pipeline gồm 6 stage, chạy theo thứ tự:

```text
preprocess → vad → asr → diarize → merge → summarize
```

Package này không truy cập database hay HTTP. Worker của backend gọi pipeline, pipeline ghi kết quả ra file JSON trong thư mục làm việc của job.

## Trạng thái các stage

| Stage | Backend `real` | Task |
|---|---|---|
| `preprocess` | Đã có: ffprobe + ffmpeg → `audio.wav` 16 kHz mono, chọn file phát lại | AI-05 |
| `vad` | Đã có: Silero VAD (qua faster-whisper), gộp region, `NO_SPEECH_DETECTED` khi dưới 0.5 s lời nói | AI-06 |
| `asr` | Đã có: faster-whisper `large-v3-turbo` int8_float16 (ADR-0001), chuẩn hóa timestamp, lọc hallucination; OOM là transient | AI-06 |
| `diarize` | Đã có: pyannote `community-1` (torch CPU), gợi ý số người nói, ghi RTTM; lỗi thì runner fallback 1 speaker | AI-07 |
| `merge` | Đã có: gán speaker cho từng word theo overlap lớn nhất, tách và gộp đoạn, cờ `overlap`/`low_confidence`, đánh số speaker theo thứ tự xuất hiện | AI-08 |
| `summarize` | Đã có: Claude API (`claude-opus-5-5`) qua `LLMProvider`, prompt `summary-v1`, hậu kiểm evidence, hạn chót, người nhận việc; mặc định tắt (`disabled`) | AI-09 |

Cả 6 stage đã có bản `real`. Dùng `PIPELINE_BACKEND=fake` để chạy trọn pipeline bằng dữ liệu mẫu, không cần model.

Stage dùng model (`vad`, `asr`, `diarize`) gọi model qua adapter trong `meeting_pipeline/engines/`, có bản fake cho test. Cài model thật bằng `uv sync --extra asr` (faster-whisper, cuBLAS, cuDNN; CI không cài). Biến môi trường của ASR, mặc định theo `docs/adr/0001-asr.md`: `ASR_MODEL` (`large-v3-turbo`), `ASR_COMPUTE_TYPE` (`int8_float16`), `ASR_DEVICE` (`cuda`), `ASR_BEAM_SIZE` (`5`).

Diarization cài bằng `uv sync --extra diarize`: pyannote.audio 4.x và torch **bản CPU** (bản torch trên PyPI kèm CUDA 13, xung đột cuDNN với CTranslate2 của extra `asr`). Model `pyannote/speaker-diarization-community-1` là model gated: tài khoản Hugging Face phải chấp nhận điều kiện, token lấy từ `HF_TOKEN` hoặc `hf auth login`. Biến: `DIARIZATION_MODEL`, `DIARIZATION_DEVICE` (`auto`).

Biến môi trường của `preprocess`: `PIPELINE_MIN_DURATION_SEC` (mặc định 1), `PIPELINE_MAX_DURATION_SEC` (mặc định 3600), `FFMPEG_BIN`, `FFPROBE_BIN`.

`merge` là pure function, không cần model: `stages/merge.py::merge(asr, diarization, audio)`. Các ngưỡng nằm trong `MergeConfig` và là giá trị khởi tạo, sẽ hiệu chỉnh sau benchmark AI-13. Output luôn thỏa bất biến của `transcript.schema.json`, kể cả khi ASR trả timestamp lệch (có property test bằng hypothesis).

### Tóm tắt bằng LLM (`summarize`)

`summarize` đọc transcript (bản đã sửa qua `transcript_override_path` nếu có), gọi LLM qua `meeting_pipeline/llm/` rồi hậu kiểm bản nháp trước khi ghi `summary.json`. Chỉ gửi **text** của transcript (kèm tên speaker, thời gian, ngày họp), không gửi audio.

| `LLM_PROVIDER` | Hành vi |
|---|---|
| không đặt, `disabled` | Không gọi LLM, không có request nào ra ngoài; `status=disabled` (PRIV-16) |
| `fake` | Bản nháp cố định, không gọi mạng (dev, CI, E2E) |
| `anthropic` | Claude API. Cài bằng `uv sync --extra llm`; credential do SDK tự tìm (`ANTHROPIC_API_KEY`). Không có credential thì cũng `disabled`, không gửi gì đi |

Biến của provider `anthropic`: `LLM_MODEL` (`claude-opus-5-5`), `LLM_EFFORT` (`medium`), `LLM_TIMEOUT_SEC` (`180`), `LLM_MAX_RETRIES` (`2`, retry trong SDK, ngoài retry của job).

- Transcript dưới 2 segment hoặc dưới 30 từ thì `insufficient_content`, không gọi LLM.
- Prompt `summary-v1` (`llm/prompts.py`) đặt transcript trong khối `<transcript>` và dặn model coi đó là dữ liệu, không làm theo lệnh nằm trong transcript. Output là structured output theo model Pydantic `SummaryDraft`.
- Hậu kiểm (`llm/postcheck.py`): bỏ evidence trỏ tới segment không tồn tại; action item không còn evidence hoặc bị bỏ hạn chót thì `needs_review=true`; `due_date` chỉ giữ khi có `due_date_text` và ngày họp; người nhận việc trùng tên speaker thì gắn `assignee_speaker_label`.
- Lỗi: 408, 409, 429, 5xx, timeout, lỗi mạng là transient `LLM_UNAVAILABLE`; 4xx khác là permanent `LLM_REQUEST_INVALID`; model từ chối, hết `max_tokens` hoặc output sai schema là `LLM_OUTPUT_INVALID`. Thông điệp lỗi và log không chứa prompt hay response.

## Cài đặt

Cần [uv](https://docs.astral.sh/uv/) và `ffmpeg`/`ffprobe` trong `PATH`.

```bash
cd pipeline
uv sync
```

## Chạy test

```bash
uv run pytest -m "not model"   # test chạy được trên CPU, không cần model thật
uv run ruff check . && uv run ruff format --check .
```

Test gắn marker `model` cần model thật hoặc GPU và chỉ chạy thủ công.

## Chạy một stage bằng CLI

Mỗi job có một thư mục làm việc chứa `job.json` (do worker ghi) và các artifact của từng stage.

```bash
# Ví dụ với fake pipeline, không cần model
mkdir -p /tmp/job1
cp ../contracts/fixtures/pipeline/job.json /tmp/job1/job.json
for s in preprocess vad asr diarize merge summarize; do
  PIPELINE_BACKEND=fake uv run python -m meeting_pipeline run-stage $s --workdir /tmp/job1
done
ls /tmp/job1   # preprocess.json vad.json asr.json diarization.json transcript.json summary.json
```

| Exit code | Ý nghĩa | Chi tiết |
|---|---|---|
| 0 | Thành công | Artifact `{stage}.json` đã được ghi atomic |
| 10 | Lỗi permanent | `<stage>.error.json`, không nên retry |
| 20 | Lỗi transient hoặc timeout | `<stage>.error.json`, có thể retry |

Stdout là các dòng JSON (`progress`, `done`). Stderr là log kỹ thuật, không chứa transcript.

### Fake pipeline

`PIPELINE_BACKEND=fake` dùng dữ liệu mẫu. Chọn kịch bản lỗi bằng `FAKE_SCENARIO`: `ok`, `slow`, `transient_once`, `permanent`, `timeout`, `no_speech`, `diarize_fail`, `summary_fail`, `summary_flaky`, `summary_disabled`. Mô tả chi tiết ở đầu file `meeting_pipeline/fake/stages.py`.

## Gọi pipeline từ worker (dành cho B)

```python
from meeting_pipeline.runner import run_job, overall_progress
from meeting_pipeline.schemas import JobSpec
from meeting_pipeline.errors import (
    PermanentPipelineError,
    TransientPipelineError,
    PipelineCancelledError,
)

spec = JobSpec(
    meeting_id=...,
    job_id=...,
    audio_path="/data/audio/<id>/original.webm",
    attempt=job.attempt,
    max_attempts=job.max_attempts,
)
try:
    outcome = run_job(
        spec,
        workdir=Path(f"/data/artifacts/{meeting_id}/{job_id}"),
        on_progress=lambda stage, v: save_progress(stage, overall_progress(stage, v)),
        on_stage_done=lambda stage, path: persist(stage, path),  # idempotent theo (job_id, stage)
        is_cancelled=lambda: job_was_cancelled(job_id),
    )
except TransientPipelineError:  # gồm StageTimeoutError: lên lịch retry
    ...
except PermanentPipelineError:  # failed ngay
    ...
except PipelineCancelledError:
    ...
```

- Mỗi stage chạy trong subprocess riêng. Quá timeout thì kill cả process group.
- Retry dùng lại cùng `workdir`: stage đã có artifact hợp lệ được bỏ qua, nhưng `on_stage_done` vẫn được gọi lại.
- Diarization lỗi ở lượt cuối (hoặc lỗi permanent) thì fallback 1 speaker, có warning `DIARIZATION_FALLBACK`.
- `from_stage="summarize"` cùng `transcript_override_path` chỉ chạy lại summarize, không chạy lại ASR.
- Mọi callback được gọi trên thread của người gọi `run_job()`.

## Contracts

Schema JSON và fixtures trong `contracts/pipeline/` được sinh từ `meeting_pipeline/schemas.py`:

```bash
uv run python -m meeting_pipeline export-contracts          # sinh lại
uv run python -m meeting_pipeline export-contracts --check  # kiểm drift
```

## Cấu trúc

```text
pipeline/
├── meeting_pipeline/   # package chính
└── tests/
    ├── unit/           # logic thuần, chạy nhanh
    ├── edge/           # audio edge case sinh bằng ffmpeg
    └── model/          # cần model thật, chạy thủ công
```
