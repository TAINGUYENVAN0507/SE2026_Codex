"""VT-018: get_db không tạo engine mới cho mỗi request (nguyên nhân 'too many clients' khi tải)."""

from app.db.session import get_engine


def test_get_engine_returns_the_same_engine_for_the_same_url() -> None:
    assert get_engine() is get_engine()
