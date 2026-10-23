"""Kiểm thử script CLI tạo user mới (BE-09)."""

import io
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.db.base import Base
from app.db.models.user import User
from app.scripts.create_user import create_user, main


@pytest.fixture
def user_db_session() -> Generator[Session, None, None]:
    """Tạo session in-memory database cho kiểm thử tạo user."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=[User.__table__])
        engine.dispose()


def test_create_user_success(user_db_session: Session) -> None:
    """Tạo user thành công lưu đúng thông tin và mật khẩu được băm bằng Argon2."""
    user = create_user(
        session=user_db_session,
        email="newbie@example.com",
        display_name="Người Mới",
        password="MySecret_2026!",
    )
    assert user.id is not None
    assert user.email == "newbie@example.com"
    assert user.display_name == "Người Mới"
    assert user.password_hash.startswith("$argon2")
    assert verify_password("MySecret_2026!", user.password_hash) is True


def test_create_user_duplicate_email_raises_error(user_db_session: Session) -> None:
    """Tạo user với email trùng lặp phải báo lỗi rõ ràng."""
    create_user(
        session=user_db_session,
        email="duplicate@example.com",
        display_name="Lần 1",
        password="Pass1_123!",
    )

    with pytest.raises(ValueError, match="đã tồn tại trong hệ thống"):
        create_user(
            session=user_db_session,
            email="duplicate@example.com",
            display_name="Lần 2",
            password="Pass2_456!",
        )


def test_create_user_empty_password_raises_error(user_db_session: Session) -> None:
    """Mật khẩu rỗng phải báo lỗi."""
    with pytest.raises(ValueError, match="Mật khẩu không được để trống"):
        create_user(
            session=user_db_session,
            email="nopass@example.com",
            display_name="Không Mật Khẩu",
            password="   ",
        )


def test_main_cli_success_and_duplicate(
    user_db_session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Kiểm tra gọi main CLI: đọc mật khẩu từ stdin, tạo thành công, email trùng thoát mã 1."""
    session_factory = sessionmaker(bind=user_db_session.get_bind())
    monkeypatch.setattr("app.scripts.create_user.get_session_factory", lambda: session_factory)

    # 1. Lần 1: Nhập mật khẩu qua stdin
    monkeypatch.setattr("sys.stdin", io.StringIO("SecretPass_123\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    main(["--email", "cli_user@example.com", "--name", "CLI User"])
    captured = capsys.readouterr()
    assert "Tạo người dùng thành công" in captured.out
    assert "cli_user@example.com" in captured.out

    # 2. Lần 2: Trùng email -> Thoát với sys.exit(1)
    monkeypatch.setattr("sys.stdin", io.StringIO("AnotherPass_456\n"))
    with pytest.raises(SystemExit) as exc_info:
        main(["--email", "cli_user@example.com", "--name", "CLI User Duplicate"])

    assert exc_info.value.code == 1
    captured_err = capsys.readouterr()
    assert "đã tồn tại trong hệ thống" in captured_err.err
