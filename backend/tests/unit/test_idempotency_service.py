"""Kiểm thử dịch vụ idempotency cho các yêu cầu POST (BE-04)."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import APIError
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.user import User
from app.services.idempotency import IdempotencyService


@pytest.fixture
def idem_db_session() -> Generator[Session, None, None]:
    """Tạo database in-memory cho kiểm thử IdempotencyService."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__, IdempotencyKey.__table__])
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    # Tạo user mẫu
    user = User(
        id=str(uuid.uuid4()),
        email="idem_user@example.com",
        display_name="Idem User",
        password_hash="mock",
    )
    session.add(user)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=[User.__table__, IdempotencyKey.__table__])
        engine.dispose()


def test_idempotency_branch_1_new_request(idem_db_session: Session) -> None:
    """Nhánh 1: Yêu cầu mới chưa tồn tại -> bắt đầu xử lý với is_replayed=False."""
    user = idem_db_session.query(User).first()
    service = IdempotencyService()

    result = service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-001",
        endpoint="/api/v1/meetings",
    )
    assert result.is_replayed is False
    assert result.record_id is not None

    record = idem_db_session.query(IdempotencyKey).filter_by(id=result.record_id).first()
    assert record is not None
    assert record.status == "processing"


def test_idempotency_branch_2_in_progress_raises_409(idem_db_session: Session) -> None:
    """Nhánh 2: Đang xử lý -> ném 409 REQUEST_IN_PROGRESS."""
    user = idem_db_session.query(User).first()
    service = IdempotencyService()

    # Bắt đầu lần 1
    service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-002",
        endpoint="/api/v1/meetings",
    )

    # Lần 2 gửi lại khi đang xử lý
    with pytest.raises(APIError) as exc_info:
        service.check_or_start(
            session=idem_db_session,
            user_id=user.id,
            key="key-002",
            endpoint="/api/v1/meetings",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "REQUEST_IN_PROGRESS"


def test_idempotency_branch_3_completed_returns_replayed_response(
    idem_db_session: Session,
) -> None:
    """Nhánh 3: Đã hoàn thành -> trả lại response cũ kèm is_replayed=True."""
    user = idem_db_session.query(User).first()
    service = IdempotencyService()

    # 1. Bắt đầu xử lý
    start_result = service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-003",
        endpoint="/api/v1/meetings",
    )

    # 2. Hoàn thành và lưu response
    cached_body = {"meeting": {"id": "m-123", "title": "Họp thử nghiệm"}}
    service.complete(
        session=idem_db_session,
        record_id=start_result.record_id,
        response_code=201,
        response_body=cached_body,
    )

    # 3. Gửi lại cùng key và endpoint
    replay_result = service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-003",
        endpoint="/api/v1/meetings",
    )

    assert replay_result.is_replayed is True
    assert replay_result.response_code == 201
    assert replay_result.response_body == cached_body


def test_idempotency_ttl_expired_allows_new_request(idem_db_session: Session) -> None:
    """Test TTL 24 giờ: sau 25 giờ bản ghi cũ hết hạn và cho phép tạo yêu cầu mới."""
    user = idem_db_session.query(User).first()
    current_time = datetime(2026, 10, 23, 10, 0, 0, tzinfo=UTC)

    def fake_clock() -> datetime:
        return current_time

    service = IdempotencyService(clock=fake_clock)

    # 1. Tạo và hoàn thành yêu cầu lúc t0
    start_result = service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-ttl",
        endpoint="/api/v1/meetings",
    )
    service.complete(
        session=idem_db_session,
        record_id=start_result.record_id,
        response_code=201,
        response_body={"meeting_id": "old-meeting"},
    )

    # 2. Tua thời gian sang 25 tiếng sau (vượt quá TTL 24 giờ)
    current_time += timedelta(hours=25)

    # 3. Gửi lại cùng key -> Hết hạn, bắt đầu chu kỳ mới với is_replayed=False
    new_result = service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-ttl",
        endpoint="/api/v1/meetings",
    )
    assert new_result.is_replayed is False
    assert new_result.record_id != start_result.record_id


def test_idempotency_fail_allows_retry(idem_db_session: Session) -> None:
    """Khi fail() được gọi do xử lý lỗi, bản ghi được xóa để cho phép thử lại."""
    user = idem_db_session.query(User).first()
    service = IdempotencyService()

    start_result = service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-fail",
        endpoint="/api/v1/meetings",
    )
    service.fail(idem_db_session, start_result.record_id)

    # Thử lại ngay sau đó
    retry_result = service.check_or_start(
        session=idem_db_session,
        user_id=user.id,
        key="key-fail",
        endpoint="/api/v1/meetings",
    )
    assert retry_result.is_replayed is False
