"""Persist các kết quả artifact của pipeline vào cơ sở dữ liệu (BE-07).

Triển khai:
- Đợt 1: persist_transcript sau stage merge:
  - Validate transcript.json theo schema pipeline.
  - Ghi ai_outputs (bản AI gốc bất biến).
  - Ghi speakers (display_name = "Speaker N").
  - Ghi segments (ai_text = text).
  - Đảm bảo idempotent theo (job_id, stage).
  - Nếu schema_version không hỗ trợ thì báo lỗi PIPELINE_OUTPUT_INVALID.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import Stage, Transcript
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ai_output import AIOutput
from app.db.models.transcript import Segment, Speaker

logger = logging.getLogger("backend.worker.persister")


def persist_transcript(
    db: Session,
    meeting_id: str,
    job_id: str,
    artifact_path: Path,
) -> None:
    """Validate và lưu trữ dữ liệu transcript sau stage merge vào cơ sở dữ liệu.

    Đảm bảo tính idempotent theo (job_id, "merge") và thực hiện trong 1 transaction.
    """
    if not artifact_path.is_file():
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.MERGE,
            f"Không tìm thấy tệp artifact: {artifact_path}",
        )

    try:
        with open(artifact_path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as exc:
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.MERGE,
            f"Không thể đọc định dạng JSON của transcript: {exc}",
        ) from exc

    # Kiểm tra schema_version hỗ trợ (chỉ chấp nhận 1.x)
    schema_version = raw_data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.startswith("1."):
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.MERGE,
            f"schema_version '{schema_version}' không được hỗ trợ (chỉ hỗ trợ 1.x)",
        )

    # Validate cấu trúc dữ liệu theo model Transcript
    try:
        transcript = Transcript.model_validate(raw_data)
    except (ValidationError, ValueError) as exc:
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.MERGE,
            f"Dữ liệu transcript.json không hợp lệ theo schema: {exc}",
        ) from exc

    # Idempotent guard: kiểm tra xem (job_id, "merge") đã được persist chưa
    existing_ai_output = db.execute(
        select(AIOutput).where(AIOutput.job_id == job_id, AIOutput.stage == "merge")
    ).scalar_one_or_none()
    if existing_ai_output is not None:
        logger.info(
            "Artifact merge của job %s đã được persist trước đó, bỏ qua để đảm bảo idempotent.",
            job_id,
        )
        return

    now = datetime.now(UTC)

    # 1. Ghi ai_outputs bất biến
    ai_output = AIOutput(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        job_id=job_id,
        stage="merge",
        payload=raw_data,
        model=transcript.models.asr,
        model_params=None,
        created_at=now,
    )
    db.add(ai_output)

    # 2. Ghi speakers
    speaker_map: dict[str, Speaker] = {}
    for idx, spk_item in enumerate(transcript.speakers):
        existing_spk = db.execute(
            select(Speaker).where(
                Speaker.meeting_id == meeting_id,
                Speaker.label == spk_item.label,
            )
        ).scalar_one_or_none()

        if existing_spk is not None:
            speaker_map[spk_item.label] = existing_spk
        else:
            display_name = f"Speaker {idx + 1}"
            new_speaker = Speaker(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                label=spk_item.label,
                default_name=display_name,
                display_name=display_name,
                version=1,
                created_at=now,
                updated_at=now,
            )
            db.add(new_speaker)
            db.flush()
            speaker_map[spk_item.label] = new_speaker

    # 3. Ghi segments
    for idx, seg_item in enumerate(transcript.segments):
        speaker_obj = speaker_map.get(seg_item.speaker_label) if seg_item.speaker_label else None
        speaker_id = speaker_obj.id if speaker_obj else None

        flags_payload = {"flags": [f.value for f in seg_item.flags]} if seg_item.flags else None

        segment = Segment(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            idx=idx,
            start_sec=seg_item.start_sec,
            end_sec=seg_item.end_sec,
            speaker_id=speaker_id,
            ai_speaker_id=speaker_id,
            text=seg_item.text,
            ai_text=seg_item.text,
            confidence=seg_item.confidence,
            flags=flags_payload,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(segment)

    db.commit()
    logger.info("Đã persist thành công transcript cho meeting %s từ job %s.", meeting_id, job_id)
