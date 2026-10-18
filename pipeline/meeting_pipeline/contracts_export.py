"""Sinh `contracts/pipeline/*.schema.json` và `contracts/fixtures/pipeline/*.json`.

Pydantic trong `schemas.py` là nguồn sự thật; các file trong `contracts/` được sinh ra
và commit để backend (B) dùng mà không cần import package này. CI chạy `--check`
để bắt trường hợp code và contract lệch nhau.

    uv run python -m meeting_pipeline.contracts_export          # ghi lại file
    uv run python -m meeting_pipeline.contracts_export --check  # chỉ kiểm drift
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from meeting_pipeline.errors import (
    ErrorCode,
    ErrorReport,
    PermanentPipelineError,
    StageTimeoutError,
)
from meeting_pipeline.fake import data
from meeting_pipeline.schemas import (
    AsrOutput,
    DiarizeOutput,
    JobSpec,
    PreprocessOutput,
    Stage,
    SummaryOutput,
    Transcript,
    VadOutput,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = Path("contracts/pipeline")
FIXTURE_DIR = Path("contracts/fixtures/pipeline")

# (tên file, model, mode). Output của stage dùng mode "serialization": mọi field đều
# required vì pipeline luôn ghi đủ field. job.json do backend viết nên field có
# default là optional.
SCHEMAS: list[tuple[str, type[BaseModel], str]] = [
    ("job", JobSpec, "validation"),
    ("preprocess", PreprocessOutput, "serialization"),
    ("vad", VadOutput, "serialization"),
    ("asr", AsrOutput, "serialization"),
    ("diarization", DiarizeOutput, "serialization"),
    ("transcript", Transcript, "serialization"),
    ("summary", SummaryOutput, "serialization"),
    ("error", ErrorReport, "serialization"),
]


def _fixtures() -> dict[str, BaseModel]:
    job = JobSpec(
        meeting_id="8f6c2a1e-0000-4000-8000-000000000001",
        job_id="c1d2e3f4-0000-4000-8000-000000000002",
        audio_path="/data/audio/8f6c2a1e-0000-4000-8000-000000000001/original.webm",
        num_speakers_hint=2,
        meeting_date=date(2026, 10, 15),
    )
    fallback = data.diarize_fallback_output()
    return {
        "job": job,
        "preprocess": data.preprocess_output(size_bytes=482_133),
        "vad": data.vad_output(),
        "asr": data.asr_output(),
        "diarization": data.diarize_output(),
        "diarization_fallback": fallback,
        "transcript": data.transcript(data.diarize_output()),
        "transcript_fallback": data.transcript(fallback),
        "summary": data.summary_output(job.meeting_date),
        "summary_insufficient": data.summary_insufficient(),
        "summary_disabled": SummaryOutput(
            status="disabled", model=None, prompt_version=None, overview=None
        ),
        "error_timeout": StageTimeoutError(Stage.ASR, timeout_sec=900).to_report(),
        "error_audio_invalid": PermanentPipelineError(
            ErrorCode.AUDIO_INVALID, Stage.PREPROCESS, "ffprobe không tìm thấy audio stream"
        ).to_report(),
    }


def fixture_schema_name(fixture: str) -> str:
    """Tên schema dùng để validate một fixture, ví dụ `summary_disabled` -> `summary`."""
    for name, _, _ in SCHEMAS:
        if fixture == name or fixture.startswith(name + "_"):
            return name
    raise KeyError(fixture)


def _dump(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def render() -> dict[Path, str]:
    """Nội dung mong đợi của mọi file contract, theo đường dẫn tương đối từ gốc repo."""
    files: dict[Path, str] = {}
    for name, model, mode in SCHEMAS:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"pipeline/{name}.schema.json",
            **model.model_json_schema(mode=mode),  # type: ignore[arg-type]
        }
        files[SCHEMA_DIR / f"{name}.schema.json"] = _dump(schema)
    for name, model in _fixtures().items():
        files[FIXTURE_DIR / f"{name}.json"] = _dump(model.model_dump(mode="json"))
    return files


def check(root: Path) -> list[Path]:
    """Trả về danh sách file bị thiếu hoặc khác với bản sinh từ code."""
    stale = []
    for rel, content in render().items():
        path = root / rel
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            stale.append(rel)
    return stale


def write(root: Path) -> list[Path]:
    written = []
    for rel, content in render().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            written.append(rel)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="gốc repo")
    parser.add_argument("--check", action="store_true", help="chỉ kiểm drift, không ghi")
    args = parser.parse_args(argv)

    if args.check:
        stale = check(args.root)
        for rel in stale:
            print(f"lệch contract: {rel}", file=sys.stderr)
        if stale:
            print("chạy lại: uv run python -m meeting_pipeline.contracts_export", file=sys.stderr)
        return 1 if stale else 0

    for rel in write(args.root):
        print(f"đã ghi {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
