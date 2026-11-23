"""Kiểm thử tìm kiếm không phân biệt hoa thường tiếng Việt trên PostgreSQL (BE-05)."""

import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.models.meeting import Meeting
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


def _client_for_user(db: Session, user: User) -> TestClient:
    """Tạo TestClient xác thực cho user trên database session thật."""
    app = create_app()

    def _get_db_override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: user
    token = create_access_token(user.id)
    return TestClient(app, cookies={"session_token": token})


def test_meeting_search_ignores_case_for_vietnamese_letters_on_postgres(
    db_session: Session,
) -> None:
    """Trên PostgreSQL với locale UTF-8, ilike tìm kiếm không phân biệt hoa thường có dấu (BE-05).

    Kiểm thử với 2 tiêu đề: 'Họp nhóm' và 'HỌP KỸ THUẬT'.
    q='HỌP' -> 2
    q='họp' -> 2
    q='kỹ' -> 1 ('HỌP KỸ THUẬT')
    q='KỸ' -> 1
    """
    # Ghi nhận thông tin locale database vào stdout / test log
    sql_locale = (
        "SELECT datname, datcollate, datctype FROM pg_database WHERE datname = current_database()"
    )
    locale_row = db_session.execute(text(sql_locale)).fetchone()
    print(f"\n[PostgreSQL Locale Info] {dict(locale_row._mapping) if locale_row else 'unknown'}")

    user = User(
        id=str(uuid.uuid4()),
        email=f"search-case-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Vietnamese Search User",
        password_hash="mock_hash",
    )
    db_session.add(user)
    db_session.commit()

    m1 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="Họp nhóm",
        source="upload",
        status="ready",
        version=1,
    )
    m2 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user.id,
        title="HỌP KỸ THUẬT",
        source="upload",
        status="ready",
        version=1,
    )
    db_session.add_all([m1, m2])
    db_session.commit()

    client = _client_for_user(db_session, user)

    # 1. q=HỌP (chữ hoa có dấu) -> Khớp cả 'Họp nhóm' và 'HỌP KỸ THUẬT' (total = 2)
    res_hop_upper = client.get("/api/v1/meetings", params={"q": "HỌP"})
    assert res_hop_upper.status_code == 200
    data_upper = res_hop_upper.json()
    assert data_upper["total"] == 2, f"Kỳ vọng 2 cuộc họp nhưng nhận {data_upper['total']}"
    assert len(data_upper["items"]) == 2

    # 2. q=họp (chữ thường có dấu) -> Khớp cả 'Họp nhóm' và 'HỌP KỸ THUẬT' (total = 2)
    res_hop_lower = client.get("/api/v1/meetings", params={"q": "họp"})
    assert res_hop_lower.status_code == 200
    data_lower = res_hop_lower.json()
    assert data_lower["total"] == 2, f"Kỳ vọng 2 cuộc họp nhưng nhận {data_lower['total']}"
    assert len(data_lower["items"]) == 2

    # 3. q=kỹ (chữ thường) -> Khớp 'HỌP KỸ THUẬT' (total = 1)
    res_ky = client.get("/api/v1/meetings", params={"q": "kỹ"})
    assert res_ky.status_code == 200
    data_ky = res_ky.json()
    assert data_ky["total"] == 1, f"Kỳ vọng 1 cuộc họp nhưng nhận {data_ky['total']}"
    assert data_ky["items"][0]["title"] == "HỌP KỸ THUẬT"

    # 4. q=KỸ (chữ hoa) -> Khớp 'HỌP KỸ THUẬT' (total = 1)
    res_ky_upper = client.get("/api/v1/meetings", params={"q": "KỸ"})
    assert res_ky_upper.status_code == 200
    data_ky_upper = res_ky_upper.json()
    assert data_ky_upper["total"] == 1
    assert data_ky_upper["items"][0]["title"] == "HỌP KỸ THUẬT"
