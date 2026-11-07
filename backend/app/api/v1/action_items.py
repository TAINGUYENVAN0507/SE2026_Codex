"""Router cho các tác vụ công việc (Action Items) trong cuộc họp."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    Response,
    status,
)
from fastapi import (
    Path as FastApiPath,
)
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.errors import APIError
from app.db.models.action_item import ActionItem
from app.db.models.meeting import Meeting
from app.db.models.transcript import Speaker
from app.db.session import get_db
from app.schemas.action_item import (
    ActionItemAiOriginal,
    ActionItemCreate,
    ActionItemListOut,
    ActionItemOut,
    ActionItemPatch,
)
from app.schemas.common import ErrorResponse
from app.services.audit import record_edit

router = APIRouter()


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


@router.get(
    "/{meeting_id}/action-items",
    response_model=ActionItemListOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
    },
    summary="Lấy danh sách các action items của cuộc họp",
)
def list_meeting_action_items(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> ActionItemListOut:
    """Lấy danh sách các action item (công việc cần làm) của cuộc họp."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    stmt = (
        select(ActionItem)
        .where(
            ActionItem.meeting_id == meeting.id,
            ActionItem.deleted_at.is_(None),
        )
        .order_by(ActionItem.created_at.asc())
    )
    items = db.execute(stmt).scalars().all()
    return ActionItemListOut(items=[serialize_action_item(item) for item in items])


@router.post(
    "/{meeting_id}/action-items",
    response_model=ActionItemOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
        422: {"model": ErrorResponse, "description": "Dữ liệu không hợp lệ"},
    },
    summary="Tạo action item mới do người dùng thêm thủ công",
)
def create_meeting_action_item(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    payload: ActionItemCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> ActionItemOut:
    """Tạo mới một action item với nguồn gốc source='user'."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    cleaned_desc = payload.description.strip()
    if not cleaned_desc:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Mô tả công việc không được để trống.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if len(cleaned_desc) > 1000:
        raise APIError(
            code="VALIDATION_ERROR",
            message="Mô tả công việc không được vượt quá 1000 ký tự.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    item_status = payload.status or "open"
    if item_status not in ("open", "done"):
        raise APIError(
            code="VALIDATION_ERROR",
            message="Trạng thái công việc chỉ có thể là 'open' hoặc 'done'.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    speaker_id = None
    assignee_name = payload.assignee_name
    if payload.assignee_speaker_id is not None:
        spk = db.execute(
            select(Speaker).where(
                Speaker.id == payload.assignee_speaker_id,
                Speaker.meeting_id == meeting.id,
            )
        ).scalar_one_or_none()
        if spk is None:
            raise APIError(
                code="SPEAKER_NOT_IN_MEETING",
                message="Người nói không thuộc cuộc họp này.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        speaker_id = spk.id
        if not assignee_name:
            assignee_name = spk.display_name

    now = datetime.now(UTC)
    new_item = ActionItem(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        description=cleaned_desc,
        assignee_name=assignee_name,
        assignee_speaker_id=speaker_id,
        due_date=payload.due_date,
        due_date_text=None,
        status=item_status,
        source="user",
        ai_original=None,
        evidence_segment_ids=[],
        needs_review=False,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(new_item)

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="action_item",
        entity_id=new_item.id,
        action="create",
        actor_id=current_user.id,
        field=None,
        before=None,
        after={
            "description": cleaned_desc,
            "status": item_status,
            "assignee_name": assignee_name,
            "assignee_speaker_id": speaker_id,
            "due_date": payload.due_date,
        },
        entity_version_after=1,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()
    db.refresh(new_item)

    return serialize_action_item(new_item)


@router.patch(
    "/{meeting_id}/action-items/{item_id}",
    response_model=ActionItemOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Không tìm thấy action item",
        },
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version của action item",
        },
    },
    summary="Chỉnh sửa action item",
)
def patch_meeting_action_item(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    item_id: Annotated[str, FastApiPath(description="UUID của action item")],
    payload: ActionItemPatch,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> ActionItemOut:
    """Chỉnh sửa thông tin action item có kiểm tra optimistic locking."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    item = db.execute(
        select(ActionItem).where(
            ActionItem.id == item_id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if item is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy công việc cần làm được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if payload.version != item.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": item.version},
            },
        )

    fields_set = payload.model_fields_set
    new_desc = item.description
    if "description" in fields_set:
        if payload.description is None:
            raise APIError(
                code="VALIDATION_ERROR",
                message="Mô tả công việc không được để trống.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        cleaned = payload.description.strip()
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
        new_desc = cleaned

    new_status = item.status
    if "status" in fields_set:
        if payload.status not in ("open", "done"):
            raise APIError(
                code="VALIDATION_ERROR",
                message="Trạng thái chỉ có thể là 'open' hoặc 'done'.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        new_status = payload.status

    new_assignee_name = item.assignee_name
    if "assignee_name" in fields_set:
        new_assignee_name = payload.assignee_name

    new_speaker_id = item.assignee_speaker_id
    if "assignee_speaker_id" in fields_set:
        if payload.assignee_speaker_id is not None:
            spk = db.execute(
                select(Speaker).where(
                    Speaker.id == payload.assignee_speaker_id,
                    Speaker.meeting_id == meeting.id,
                )
            ).scalar_one_or_none()
            if spk is None:
                raise APIError(
                    code="SPEAKER_NOT_IN_MEETING",
                    message="Người nói không thuộc cuộc họp này.",
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            new_speaker_id = spk.id
            if "assignee_name" not in fields_set and not new_assignee_name:
                new_assignee_name = spk.display_name
        else:
            new_speaker_id = None

    new_due_date = item.due_date
    if "due_date" in fields_set:
        new_due_date = payload.due_date

    # Kiểm tra no-op (không đổi giá trị)
    if (
        new_desc == item.description
        and new_status == item.status
        and new_assignee_name == item.assignee_name
        and new_speaker_id == item.assignee_speaker_id
        and new_due_date == item.due_date
    ):
        return serialize_action_item(item)

    now = datetime.now(UTC)
    new_version = payload.version + 1

    stmt = (
        update(ActionItem)
        .where(
            ActionItem.id == item.id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.version == payload.version,
            ActionItem.deleted_at.is_(None),
        )
        .values(
            description=new_desc,
            status=new_status,
            assignee_name=new_assignee_name,
            assignee_speaker_id=new_speaker_id,
            due_date=new_due_date,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        current_item = db.execute(
            select(ActionItem).where(
                ActionItem.id == item.id,
                ActionItem.meeting_id == meeting.id,
                ActionItem.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        curr_ver = current_item.version if current_item else payload.version
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": curr_ver},
            },
        )

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="action_item",
        entity_id=item.id,
        action="update",
        actor_id=current_user.id,
        field=None,
        before={
            "description": item.description,
            "status": item.status,
            "assignee_name": item.assignee_name,
            "assignee_speaker_id": item.assignee_speaker_id,
            "due_date": item.due_date,
        },
        after={
            "description": new_desc,
            "status": new_status,
            "assignee_name": new_assignee_name,
            "assignee_speaker_id": new_speaker_id,
            "due_date": new_due_date,
        },
        entity_version_after=new_version,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()
    db.refresh(item)

    return serialize_action_item(item)


@router.delete(
    "/{meeting_id}/action-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Không tìm thấy action item",
        },
        409: {
            "model": ErrorResponse,
            "description": "Xung đột phiên bản version khi xóa",
        },
    },
    summary="Xóa action item (xóa mềm có audit)",
)
def delete_meeting_action_item(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    item_id: Annotated[str, FastApiPath(description="UUID của action item")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
    version: Annotated[int | None, Query(description="Phiên bản của action item")] = None,
) -> Response:
    """Xóa action item (xóa mềm) có kiểm tra version nếu được cung cấp."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    item = db.execute(
        select(ActionItem).where(
            ActionItem.id == item_id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if item is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy công việc cần làm được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if version is not None and version != item.version:
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": item.version},
            },
        )

    now = datetime.now(UTC)
    new_version = item.version + 1

    expected_ver = version if version is not None else item.version
    stmt = (
        update(ActionItem)
        .where(
            ActionItem.id == item.id,
            ActionItem.meeting_id == meeting.id,
            ActionItem.version == expected_ver,
            ActionItem.deleted_at.is_(None),
        )
        .values(
            deleted_at=now,
            version=new_version,
            updated_at=now,
        )
    )
    res = db.execute(stmt)
    if res.rowcount == 0:
        db.rollback()
        current_item = db.execute(
            select(ActionItem).where(
                ActionItem.id == item.id,
                ActionItem.meeting_id == meeting.id,
            )
        ).scalar_one_or_none()
        curr_ver = current_item.version if current_item else item.version
        raise APIError(
            code="VERSION_CONFLICT",
            message="Action item đã được cập nhật ở nơi khác. Vui lòng tải lại.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "entity": "action_item",
                "current": {"id": item.id, "version": curr_ver},
            },
        )

    record_edit(
        db,
        meeting_id=meeting.id,
        entity_type="action_item",
        entity_id=item.id,
        action="delete",
        actor_id=current_user.id,
        field=None,
        before={
            "description": item.description,
            "status": item.status,
            "assignee_name": item.assignee_name,
        },
        after={"deleted_at": now.isoformat()},
        entity_version_after=new_version,
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        created_at=now,
    )
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
