"""Dịch vụ nghiệp vụ và chuyển đổi dữ liệu cho tác vụ công việc (Action Items) (AD-018, BE-12)."""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.action_item import ActionItem
from app.db.models.transcript import Segment, Speaker
from app.schemas.action_item import (
    ActionItemAiOriginal,
    ActionItemOut,
)


def serialize_action_item(item: ActionItem) -> ActionItemOut:
    """Chuyển đổi ActionItem model sang ActionItemOut schema."""
    ai_orig = None
    if item.ai_original and isinstance(item.ai_original, dict):
        # Snapshot worker có thêm metadata; chỉ chiếu field thuộc contract phản hồi.
        ai_orig = ActionItemAiOriginal.model_validate(
            {
                key: value
                for key, value in item.ai_original.items()
                if key in ActionItemAiOriginal.model_fields
            }
        )

    if item.source == "ai" and item.ai_original:
        is_edited = (
            item.description != item.ai_original.get("description")
            or item.assignee_name != item.ai_original.get("assignee_name")
            or item.due_date != item.ai_original.get("due_date")
        )
    else:
        is_edited = item.version > 1

    return ActionItemOut(
        id=item.id,
        meeting_id=item.meeting_id,
        description=item.description,
        assignee_name=item.assignee_name,
        assignee_speaker_id=item.assignee_speaker_id,
        due_date=item.due_date,
        due_date_text=item.due_date_text,
        status=item.status,
        source=item.source,  # type: ignore[arg-type]
        is_edited=is_edited,
        needs_review=item.needs_review,
        evidence_segment_ids=item.evidence_segment_ids or [],
        ai_original=ai_orig,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def validate_description(description: str | None) -> str:
    """Kiểm tra và chuẩn hóa mô tả action item."""
    if description is None:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Mô tả công việc không được để trống.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    cleaned = description.strip()
    if not cleaned:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Mô tả công việc không được để trống.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if len(cleaned) > 1000:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Mô tả công việc không được vượt quá 1000 ký tự.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return cleaned


def validate_status(item_status: str | None) -> str:
    """Kiểm tra trạng thái hợp lệ của action item ('open' hoặc 'done')."""
    st = item_status or "open"
    if st not in ("open", "done"):
        raise APIError(
            code="VALIDATION_ERROR",
            message="Trạng thái công việc chỉ có thể là 'open' hoặc 'done'.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return st


def validate_assignee_speaker(
    db: Session,
    meeting_id: str,
    speaker_id: str | None,
    assignee_name: str | None = None,
) -> tuple[str | None, str | None]:
    """Xác thực người nói được gán thuộc cuộc họp và đồng bộ tên hiển thị."""
    if speaker_id is None:
        return None, assignee_name

    spk = db.execute(
        select(Speaker).where(
            Speaker.id == speaker_id,
            Speaker.meeting_id == meeting_id,
        )
    ).scalar_one_or_none()
    if spk is None:
        raise APIError(
            code="SPEAKER_NOT_IN_MEETING",
            message="Người nói không thuộc cuộc họp này.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    resolved_name = assignee_name if assignee_name else spk.display_name
    return spk.id, resolved_name


def validate_evidence_segments(
    db: Session,
    meeting_id: str,
    segment_ids: list[str],
) -> list[str]:
    """Xác thực danh sách đoạn thoại bằng chứng thuộc cuộc họp."""
    if not segment_ids:
        return []

    existing = (
        db.execute(
            select(Segment.id).where(
                Segment.id.in_(segment_ids),
                Segment.meeting_id == meeting_id,
            )
        )
        .scalars()
        .all()
    )
    existing_set = set(existing)
    invalid = [sid for sid in segment_ids if sid not in existing_set]
    if invalid:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Một số đoạn thoại bằng chứng không tồn tại trong cuộc họp.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"invalid_segment_ids": invalid},
        )
    return segment_ids
