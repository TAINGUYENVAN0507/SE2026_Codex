"""Dịch vụ thực thi chính sách lưu trữ (Retention Policy) cho audio và dữ liệu vận hành (BE-14).

Bao gồm:
- Dọn dẹp tệp âm thanh và artifacts của cuộc họp khi quá hạn retention_until.
- Đặt meeting.audio_path = None để audio.available trở thành false.
- Transcript và tóm tắt trong DB được giữ lại cho tới khi người dùng chủ động xóa.
- Bỏ qua các cuộc họp đang có tiến trình job active (queued, running, retry_scheduled).
- Xóa các bản ghi idempotency_keys quá hạn lưu trữ vận hành (OPERATIONAL_RETENTION_DAYS).
- Hỗ trợ cờ dry_run để kiểm tra mà không thay đổi dữ liệu hay ổ đĩa.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.services.storage import Storage

logger = logging.getLogger("backend.services.retention")


@dataclass
class CleanupResult:
    """Kết quả thống kê sau khi chạy tiến trình dọn dẹp dữ liệu hết hạn."""

    audio_expired_meetings: int
    operational_keys_cleaned: int
    dry_run: bool


def run_retention_cleanup(
    db: Session,
    storage: Storage,
    now: datetime | None = None,
    dry_run: bool = False,
) -> CleanupResult:
    """Quét và dọn dẹp các tệp audio/artifacts và idempotency_keys hết hạn.

    Args:
        db: Session cơ sở dữ liệu SQLAlchemy.
        storage: Dịch vụ lưu trữ tệp (Storage).
        now: Mốc thời gian UTC phục vụ kiểm thử (nếu None sẽ lấy datetime.now(timezone.utc)).
        dry_run: Nếu True, chỉ thống kê và log, không xóa tệp và không ghi DB.

    Returns:
        CleanupResult chứa số lượng tài nguyên đã xử lý.
    """
    settings = get_settings()
    current_time = now if now is not None else datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)

    # 1. Tìm các meeting có job đang active để bỏ qua
    active_meeting_ids = set(
        db.execute(
            select(Job.meeting_id).where(Job.status.in_(["queued", "running", "retry_scheduled"]))
        )
        .scalars()
        .all()
    )

    # 2. Tìm các cuộc họp đã hết hạn audio: retention_until < current_time và audio_path có giá trị
    # Quy tắc biên: đúng lúc retention_until thì chưa xóa (retention_until < current_time)
    expired_meetings = (
        db.execute(
            select(Meeting).where(
                Meeting.retention_until.is_not(None),
                Meeting.retention_until < current_time,
                Meeting.audio_path.is_not(None),
            )
        )
        .scalars()
        .all()
    )

    audio_cleaned_count = 0
    for meeting in expired_meetings:
        if meeting.id in active_meeting_ids:
            logger.info(
                "Bỏ qua dọn dẹp audio cuộc họp %s vì đang có job active",
                meeting.id,
            )
            continue

        audio_cleaned_count += 1
        if dry_run:
            logger.info("[dry-run] Sẽ xóa audio và artifacts của cuộc họp: %s", meeting.id)
        else:
            # Xóa file audio và artifacts trên ổ đĩa
            storage.delete_meeting_files(meeting.id)
            # Cập nhật DB: đặt audio_path = None
            meeting.audio_path = None
            meeting.updated_at = current_time
            logger.info("Đã dọn dẹp audio và artifacts hết hạn của cuộc họp: %s", meeting.id)

    # 3. Dọn dẹp dữ liệu vận hành (idempotency_keys)
    op_days = settings.OPERATIONAL_RETENTION_DAYS
    op_cutoff = current_time - timedelta(days=op_days)

    expired_idem_ids = (
        db.execute(select(IdempotencyKey.id).where(IdempotencyKey.created_at < op_cutoff))
        .scalars()
        .all()
    )

    idempotency_cleaned_count = len(expired_idem_ids)
    if idempotency_cleaned_count > 0:
        if dry_run:
            logger.info(
                "[dry-run] Sẽ xóa %d idempotency_keys cũ hơn %d ngày (trước %s)",
                idempotency_cleaned_count,
                op_days,
                op_cutoff.isoformat(),
            )
        else:
            db.execute(delete(IdempotencyKey).where(IdempotencyKey.id.in_(expired_idem_ids)))
            logger.info(
                "Đã xóa %d idempotency_keys cũ hơn %d ngày",
                idempotency_cleaned_count,
                op_days,
            )

    if not dry_run:
        db.commit()

    return CleanupResult(
        audio_expired_meetings=audio_cleaned_count,
        operational_keys_cleaned=idempotency_cleaned_count,
        dry_run=dry_run,
    )
