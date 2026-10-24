"""Persist các kết quả artifact của pipeline vào cơ sở dữ liệu (BE-07).

Triển khai:
- Đợt 1: persist_transcript sau stage merge:
  - Validate transcript.json theo schema pipeline.
  - Ghi ai_outputs (bản AI gốc bất biến).
  - Ghi speakers (display_name = "Speaker N").
  - Ghi segments (ai_text = text).
  - Đảm bảo idempotent theo (job_id, stage).
  - Nếu schema_version không hỗ trợ thì báo lỗi PIPELINE_OUTPUT_INVALID.
- Đợt 2: persist_summary sau stage summarize:
  - Validate summary.json theo schema pipeline.
  - Ghi ai_outputs, summary (status: ready, disabled, insufficient_content).
  - Đổi evidence_segment_indices sang evidence_segment_ids (UUID của segment).
  - Nếu evidence trỏ tới index không tồn tại: bỏ evidence đó và đặt needs_review=True.
  - Ghi action_items (source=ai, ai_original).
  - Đảm bảo idempotent theo (job_id, stage).
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import Stage, SummaryOutput, Transcript
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.action_item import ActionItem
from app.db.models.ai_output import AIOutput
from app.db.models.summary import Summary
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
            f"Không tìm thấy tệp artifact: {artifact_path.name}",
        )

    try:
        with open(artifact_path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as exc:
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.MERGE,
            f"Không thể đọc định dạng JSON của {artifact_path.name}",
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
        err_count = exc.error_count() if isinstance(exc, ValidationError) else 1
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.MERGE,
            f"artifact {artifact_path.name} sai schema ({err_count} lỗi)",
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


def persist_summary(
    db: Session,
    meeting_id: str,
    job_id: str,
    artifact_path: Path,
) -> None:
    """Validate và lưu trữ dữ liệu summary và action items sau stage summarize vào cơ sở dữ liệu.

    Đảm bảo tính idempotent theo (job_id, "summarize") và thực hiện trong 1 transaction.
    """
    if not artifact_path.is_file():
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.SUMMARIZE,
            f"Không tìm thấy tệp artifact: {artifact_path.name}",
        )

    try:
        with open(artifact_path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as exc:
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.SUMMARIZE,
            f"Không thể đọc định dạng JSON của {artifact_path.name}",
        ) from exc

    schema_version = raw_data.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.startswith("1."):
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.SUMMARIZE,
            f"schema_version '{schema_version}' không được hỗ trợ (chỉ hỗ trợ 1.x)",
        )

    try:
        summary_output = SummaryOutput.model_validate(raw_data)
    except (ValidationError, ValueError) as exc:
        err_count = exc.error_count() if isinstance(exc, ValidationError) else 1
        raise PermanentPipelineError(
            ErrorCode.PIPELINE_OUTPUT_INVALID,
            Stage.SUMMARIZE,
            f"artifact {artifact_path.name} sai schema ({err_count} lỗi)",
        ) from exc

    # Idempotent guard
    existing_ai_output = db.execute(
        select(AIOutput).where(AIOutput.job_id == job_id, AIOutput.stage == "summarize")
    ).scalar_one_or_none()
    if existing_ai_output is not None:
        logger.info(
            "Artifact summarize của job %s đã được persist trước đó, bỏ qua để đảm bảo idempotent.",
            job_id,
        )
        return

    now = datetime.now(UTC)

    # 1. Ghi ai_outputs bất biến
    ai_output = AIOutput(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        job_id=job_id,
        stage="summarize",
        payload=raw_data,
        model=summary_output.model,
        model_params=None,
        created_at=now,
    )
    db.add(ai_output)

    # Lấy mapping từ segment index sang segment UUID
    segments = db.execute(select(Segment).where(Segment.meeting_id == meeting_id)).scalars().all()
    index_to_segment_id = {seg.idx: seg.id for seg in segments}

    # Lấy mapping từ speaker label sang speaker UUID
    speakers = db.execute(select(Speaker).where(Speaker.meeting_id == meeting_id)).scalars().all()
    speaker_label_to_id = {spk.label: spk.id for spk in speakers}

    # Chuyển đổi content cho summary
    if summary_output.status == "ready":
        key_points = []
        for kp in summary_output.key_points:
            evidence_ids = [
                index_to_segment_id[idx]
                for idx in kp.evidence_segment_indices
                if idx in index_to_segment_id
            ]
            key_points.append(
                {
                    "text": kp.text,
                    "evidence_segment_ids": evidence_ids,
                }
            )

        decisions = []
        for dec in summary_output.decisions:
            evidence_ids = [
                index_to_segment_id[idx]
                for idx in dec.evidence_segment_indices
                if idx in index_to_segment_id
            ]
            decisions.append(
                {
                    "text": dec.text,
                    "evidence_segment_ids": evidence_ids,
                }
            )

        content_dict = {
            "overview": summary_output.overview,
            "key_points": key_points,
            "decisions": decisions,
        }
    else:
        content_dict = None

    # Ghi hoặc cập nhật summary của cuộc họp
    existing_summary = db.execute(
        select(Summary).where(Summary.meeting_id == meeting_id)
    ).scalar_one_or_none()

    if existing_summary is not None:
        existing_summary.status = summary_output.status
        existing_summary.content = content_dict
        existing_summary.ai_content = content_dict
        existing_summary.model = summary_output.model
        existing_summary.prompt_version = summary_output.prompt_version
        existing_summary.updated_at = now
    else:
        new_summary = Summary(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            status=summary_output.status,
            content=content_dict,
            ai_content=content_dict,
            model=summary_output.model,
            prompt_version=summary_output.prompt_version,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(new_summary)

    # Ghi action items
    for item in summary_output.action_items:
        evidence_ids = []
        item_needs_review = item.needs_review
        for idx in item.evidence_segment_indices:
            if idx in index_to_segment_id:
                evidence_ids.append(index_to_segment_id[idx])
            else:
                item_needs_review = True

        assignee_speaker_id = (
            speaker_label_to_id.get(item.assignee_speaker_label)
            if item.assignee_speaker_label
            else None
        )

        due_date_str = item.due_date.isoformat() if item.due_date else None

        ai_original = {
            "description": item.description,
            "assignee_name": item.assignee_name,
            "assignee_speaker_id": assignee_speaker_id,
            "due_date": due_date_str,
            "due_date_text": item.due_date_text,
            "evidence_segment_ids": evidence_ids,
            "needs_review": item_needs_review,
        }

        action_item = ActionItem(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            description=item.description,
            assignee_name=item.assignee_name,
            assignee_speaker_id=assignee_speaker_id,
            due_date=due_date_str,
            due_date_text=item.due_date_text,
            status="open",
            source="ai",
            ai_original=ai_original,
            evidence_segment_ids=evidence_ids,
            needs_review=item_needs_review,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(action_item)

    db.commit()
    logger.info("Đã persist thành công summary cho meeting %s từ job %s.", meeting_id, job_id)
