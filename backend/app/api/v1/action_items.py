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
from app.db.session import get_db
from app.schemas.action_item import (
    ActionItemCreate,
    ActionItemListOut,
    ActionItemOut,
    ActionItemPatch,
)
from app.schemas.common import ErrorResponse
from app.services.action_items import (
    serialize_action_item,
    validate_assignee_speaker,
    validate_description,
    validate_status,
)
from app.services.audit import record_edit

router = APIRouter()


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

    cleaned_desc = validate_description(payload.description)
    item_status = validate_status(payload.status)
    speaker_id, assignee_name = validate_assignee_speaker(
        db,
        meeting.id,
        payload.assignee_speaker_id,
        payload.assignee_name,
    )

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
        new_desc = validate_description(payload.description)

    new_status = item.status
    if "status" in fields_set:
        new_status = validate_status(payload.status)

    new_assignee_name = item.assignee_name
    if "assignee_name" in fields_set:
        new_assignee_name = payload.assignee_name

    new_speaker_id = item.assignee_speaker_id
    if "assignee_speaker_id" in fields_set:
        new_speaker_id, speaker_name = validate_assignee_speaker(
            db,
            meeting.id,
            payload.assignee_speaker_id,
        )
        if "assignee_name" not in fields_set and not new_assignee_name:
            new_assignee_name = speaker_name

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
