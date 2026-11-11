"""Router lấy lịch sử chỉnh sửa audit (Edits) của cuộc họp (BE-12)."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from fastapi import (
    Path as FastApiPath,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.errors import APIError
from app.db.models.edit_event import EditEvent
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.edit import EditActorOut, EditEventOut, EditListOut

router = APIRouter()


@router.get(
    "/{meeting_id}/edits",
    response_model=EditListOut,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Không tìm thấy cuộc họp"},
    },
    summary="Lấy lịch sử chỉnh sửa audit của cuộc họp",
)
def list_meeting_edits(
    meeting_id: Annotated[str, FastApiPath(description="UUID của cuộc họp")],
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    entity_type: Annotated[str | None, Query(description="Lọc theo loại entity")] = None,
    entity_id: Annotated[str | None, Query(description="Lọc theo ID entity")] = None,
    field: Annotated[str | None, Query(description="Lọc theo trường sửa")] = None,
    page: Annotated[int, Query(ge=1, description="Số trang")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Kích thước trang")] = 10,
    limit: Annotated[int | None, Query(ge=1, le=100, description="Số bản ghi tối đa")] = None,
    offset: Annotated[int | None, Query(ge=0, description="Vị trí bắt đầu")] = None,
) -> EditListOut:
    """Lấy danh sách các sự kiện chỉnh sửa audit của cuộc họp."""
    meeting = db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.owner_id == current_user.id)
    ).scalar_one_or_none()
    if meeting is None:
        raise APIError(
            code="NOT_FOUND",
            message="Không tìm thấy cuộc họp được yêu cầu.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    stmt = select(EditEvent).where(EditEvent.meeting_id == meeting.id)

    if entity_type:
        stmt = stmt.where(EditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(EditEvent.entity_id == entity_id)
    if field:
        stmt = stmt.where(EditEvent.field == field)

    total_count = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0

    take = limit if limit is not None else page_size
    skip = offset if offset is not None else (page - 1) * page_size

    stmt = stmt.order_by(EditEvent.created_at.desc(), EditEvent.id.desc()).offset(skip).limit(take)
    events = db.execute(stmt).scalars().all()

    actor_ids = {ev.actor_id for ev in events if ev.actor_id}
    users_by_id: dict[str, User] = {}
    if actor_ids:
        users = db.execute(select(User).where(User.id.in_(actor_ids))).scalars().all()
        users_by_id = {u.id: u for u in users}

    items_out = []
    for ev in events:
        actor_name = "Unknown"
        actor_id_val = ev.actor_id or "system"
        if ev.actor_id and ev.actor_id in users_by_id:
            actor_name = users_by_id[ev.actor_id].display_name
        elif ev.actor_id == current_user.id:
            actor_name = current_user.display_name

        items_out.append(
            EditEventOut(
                id=ev.id,
                meeting_id=ev.meeting_id,
                entity_type=ev.entity_type,
                entity_id=ev.entity_id,
                action=ev.action,
                field=ev.field,
                before=ev.before,
                after=ev.after,
                actor=EditActorOut(id=actor_id_val, display_name=actor_name),
                entity_version_after=ev.entity_version_after or 1,
                request_id=ev.request_id,
                created_at=ev.created_at,
            )
        )

    return EditListOut(items=items_out, total=total_count)
