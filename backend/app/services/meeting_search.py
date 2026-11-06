"""Dịch vụ tìm kiếm, lọc và phân trang cuộc họp (VT-017).

Tuân thủ kiến trúc: logic đặt trong services, router chỉ gọi service.
Đảm bảo:
- Owner scoping bắt buộc (không rò rỉ dữ liệu giữa các người dùng).
- Thứ tự kết quả ổn định với secondary tie-breaker (Meeting.id).
- Tương thích ngược hoàn toàn với schema của client cũ.
- Xử lý an toàn wildcard và khoảng trắng khi tìm kiếm từ khóa.
"""

from datetime import date
from typing import Literal

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.db.models.meeting import Meeting
from app.schemas.meeting import MeetingSource, MeetingStatus

SortColumn = Literal["created_at", "updated_at", "title", "meeting_date"]
SortOrder = Literal["asc", "desc"]


def search_meetings(
    db: Session,
    owner_id: str,
    page: int = 1,
    page_size: int = 10,
    status: MeetingStatus | None = None,
    q: str | None = None,
    source: MeetingSource | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    sort_by: SortColumn = "created_at",
    order: SortOrder = "desc",
) -> tuple[list[Meeting], int]:
    """Tìm kiếm, lọc và phân trang danh sách cuộc họp có thứ tự ổn định.

    Args:
        db: SQLAlchemy database session.
        owner_id: ID của người dùng sở hữu (bảo vệ owner scoping).
        page: Số thứ tự trang (>= 1).
        page_size: Số lượng mục trên mỗi trang (1-100).
        status: Bộ lọc trạng thái cuộc họp.
        q: Từ khóa tìm kiếm theo tiêu đề.
        source: Bộ lọc nguồn audio (upload / recording).
        from_date: Ngày bắt đầu (YYYY-MM-DD).
        to_date: Ngày kết thúc (YYYY-MM-DD).
        sort_by: Trường sắp xếp chính (created_at, updated_at, title, meeting_date).
        order: Chiều sắp xếp (asc hoặc desc).

    Returns:
        tuple[list[Meeting], int]: Danh sách cuộc họp của trang hiện tại và tổng số mục thỏa mãn.
    """
    # 1. Bắt buộc cô lập theo chủ sở hữu (Owner Scoping Invariant)
    base_query = select(Meeting).where(Meeting.owner_id == owner_id)

    # 2. Lọc theo trạng thái
    if status is not None:
        base_query = base_query.where(Meeting.status == status)

    # 3. Lọc theo nguồn
    if source is not None:
        base_query = base_query.where(Meeting.source == source)

    # 4. Tìm kiếm từ khóa: strip khoảng trắng và escape SQL wildcards
    if q and q.strip():
        cleaned_q = q.strip()
        escaped_q = cleaned_q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        base_query = base_query.where(Meeting.title.ilike(f"%{escaped_q}%", escape="\\"))

    # 5. Lọc theo khoảng ngày (dùng meeting_date hoặc fallback sang ngày của created_at)
    date_col = func.coalesce(
        Meeting.meeting_date,
        func.substr(cast(Meeting.created_at, String), 1, 10),
    )
    if from_date is not None:
        base_query = base_query.where(date_col >= from_date.isoformat())
    if to_date is not None:
        base_query = base_query.where(date_col <= to_date.isoformat())

    # 6. Đếm tổng số bản ghi thỏa mãn điều kiện lọc
    total = db.scalar(select(func.count()).select_from(base_query.subquery())) or 0

    # 7. Sắp xếp kết quả có tie-breaker cố định (Meeting.id) để đảm bảo ổn định tuyệt đối
    sort_column_map = {
        "created_at": Meeting.created_at,
        "updated_at": Meeting.updated_at,
        "title": Meeting.title,
        "meeting_date": Meeting.meeting_date,
    }
    primary_column = sort_column_map.get(sort_by, Meeting.created_at)

    if order == "asc":
        query_ordered = base_query.order_by(primary_column.asc(), Meeting.id.asc())
    else:
        query_ordered = base_query.order_by(primary_column.desc(), Meeting.id.desc())

    # 8. Phân trang
    offset = (page - 1) * page_size
    meetings = db.execute(query_ordered.offset(offset).limit(page_size)).scalars().all()

    return list(meetings), total
