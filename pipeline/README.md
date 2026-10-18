# meeting_pipeline

Pipeline AI/Speech của *Vietnamese Meeting Minutes Assistant*. Owner: member C. Reviewer: member B.

Pipeline gồm 6 stage, chạy theo thứ tự:

```text
preprocess → vad → asr → diarize → merge → summarize
```

Package này không truy cập database hay HTTP. Worker của backend gọi pipeline, pipeline ghi kết quả ra file JSON trong thư mục làm việc của job.

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
