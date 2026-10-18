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

## Cấu trúc

```text
pipeline/
├── meeting_pipeline/   # package chính
└── tests/
    ├── unit/           # logic thuần, chạy nhanh
    ├── edge/           # audio edge case sinh bằng ffmpeg
    └── model/          # cần model thật, chạy thủ công
```
