"""Kiểm thử tính năng tìm kiếm có lọc, phân trang và thứ tự kết quả ổn định (VT-017).

Bộ test áp dụng kỹ thuật Boundary Value Analysis (BVA), kiểm thử backward compatibility,
kiểm tra thứ tự kết quả ổn định (deterministic tie-breaker), và bảo vệ owner scoping.
"""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.schemas.meeting import MeetingListOut


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Tạo database SQLite in-memory độc lập cho mỗi test case."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        IdempotencyKey.__table__,
        Speaker.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=tables)
        engine.dispose()


@pytest.fixture
def user_a(test_db: Session) -> User:
    """Tạo User A."""
    user = User(
        id=str(uuid.uuid4()),
        email="user_a@example.com",
        display_name="User A",
        password_hash="mock_hash_a",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def user_b(test_db: Session) -> User:
    """Tạo User B."""
    user = User(
        id=str(uuid.uuid4()),
        email="user_b@example.com",
        display_name="User B",
        password_hash="mock_hash_b",
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def client_a(test_db: Session, user_a: User) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User A."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_a

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(user_a.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(test_db: Session, user_b: User) -> Generator[TestClient, None, None]:
    """TestClient xác thực với User B."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    def _override_current_user() -> User:
        return user_b

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user

    token = create_access_token(user_b.id)
    with TestClient(app, cookies={"session_token": token}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(test_db: Session) -> Generator[TestClient, None, None]:
    """TestClient không có thông tin xác thực."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==============================================================================
# NHÓM 1: BOUNDARY VALUE ANALYSIS (BVA) CHO PHÂN TRANG (PAGE & PAGE_SIZE)
# ==============================================================================


def test_bva_page_min_valid(client_a: TestClient, test_db: Session, user_a: User) -> None:
    """TC01: [BVA] Biên dưới hợp lệ của page: page=1."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp kiểm thử page biên dưới",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(meeting)
    test_db.commit()

    res = client_a.get("/api/v1/meetings?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_bva_page_invalid_zero(client_a: TestClient) -> None:
    """TC02: [BVA] Dưới biên của page: page=0 (không hợp lệ vì ge=1)."""
    res = client_a.get("/api/v1/meetings?page=0")
    assert res.status_code == 422


def test_bva_page_invalid_negative(client_a: TestClient) -> None:
    """TC03: [BVA] Giá trị âm của page: page=-1 (không hợp lệ vì ge=1)."""
    res = client_a.get("/api/v1/meetings?page=-1")
    assert res.status_code == 422


def test_bva_page_size_min_valid(client_a: TestClient, test_db: Session, user_a: User) -> None:
    """TC04: [BVA] Biên dưới hợp lệ của page_size: page_size=1."""
    for i in range(3):
        test_db.add(
            Meeting(
                id=str(uuid.uuid4()),
                owner_id=user_a.id,
                title=f"Cuộc họp số {i}",
                source="upload",
                status="ready",
                version=1,
            )
        )
    test_db.commit()

    res = client_a.get("/api/v1/meetings?page=1&page_size=1")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total"] == 3
    assert len(data["items"]) == 1


def test_bva_page_size_invalid_zero(client_a: TestClient) -> None:
    """TC05: [BVA] Dưới biên của page_size: page_size=0 (không hợp lệ vì ge=1)."""
    res = client_a.get("/api/v1/meetings?page_size=0")
    assert res.status_code == 422


def test_bva_page_size_max_valid(client_a: TestClient, test_db: Session, user_a: User) -> None:
    """TC06: [BVA] Biên trên hợp lệ của page_size: page_size=100."""
    res = client_a.get("/api/v1/meetings?page_size=100")
    assert res.status_code == 200
    data = res.json()
    assert data["page_size"] == 100


def test_bva_page_size_invalid_above_max(client_a: TestClient) -> None:
    """TC07: [BVA] Vượt biên trên của page_size: page_size=101 (không hợp lệ vì le=100)."""
    res = client_a.get("/api/v1/meetings?page_size=101")
    assert res.status_code == 422


# ==============================================================================
# NHÓM 2: THỨ TỰ KẾT QUẢ ỔN ĐỊNH VỚI DETERMINISTIC TIE-BREAKER
# ==============================================================================


def test_stable_result_ordering_deterministic_tiebreaker(
    client_a: TestClient, test_db: Session, user_a: User
) -> None:
    """TC08: Thứ tự kết quả ổn định tuyệt đối khi nhiều bản ghi có cùng created_at và meeting_date.

    Đảm bảo secondary tie-breaker (Meeting.id) ngăn chặn hoàn toàn hiện tượng
    trùng lặp bản ghi hoặc sót bản ghi giữa các trang khi phân trang.
    """
    fixed_time = datetime(2026, 11, 6, 10, 0, 0, tzinfo=UTC)
    meeting_ids = []

    # Tạo 15 cuộc họp có created_at giống hệt nhau
    for i in range(15):
        m_id = str(uuid.uuid4())
        meeting_ids.append(m_id)
        test_db.add(
            Meeting(
                id=m_id,
                owner_id=user_a.id,
                title=f"Đồng thời {i:02d}",
                source="upload",
                status="ready",
                meeting_date="2026-11-06",
                created_at=fixed_time,
                updated_at=fixed_time,
                version=1,
            )
        )
    test_db.commit()

    # Duyệt 3 trang, mỗi trang 5 mục
    res_p1 = client_a.get("/api/v1/meetings?page=1&page_size=5&sort_by=created_at&order=desc")
    res_p2 = client_a.get("/api/v1/meetings?page=2&page_size=5&sort_by=created_at&order=desc")
    res_p3 = client_a.get("/api/v1/meetings?page=3&page_size=5&sort_by=created_at&order=desc")

    assert res_p1.status_code == 200
    assert res_p2.status_code == 200
    assert res_p3.status_code == 200

    items_p1 = res_p1.json()["items"]
    items_p2 = res_p2.json()["items"]
    items_p3 = res_p3.json()["items"]

    ids_p1 = [m["id"] for m in items_p1]
    ids_p2 = [m["id"] for m in items_p2]
    ids_p3 = [m["id"] for m in items_p3]

    assert len(ids_p1) == 5
    assert len(ids_p2) == 5
    assert len(ids_p3) == 5

    # 1. Các trang phân biệt hoàn toàn, không có id nào bị lặp lại
    assert set(ids_p1).isdisjoint(set(ids_p2)), (
        "Phát hiện bản ghi trùng lặp giữa trang 1 và trang 2!"
    )
    assert set(ids_p2).isdisjoint(set(ids_p3)), (
        "Phát hiện bản ghi trùng lặp giữa trang 2 và trang 3!"
    )
    assert set(ids_p1).isdisjoint(set(ids_p3)), (
        "Phát hiện bản ghi trùng lặp giữa trang 1 và trang 3!"
    )

    # 2. Toàn bộ 15 bản ghi được bao phủ trọn vẹn, không sót bản ghi nào
    all_returned_ids = set(ids_p1 + ids_p2 + ids_p3)
    assert all_returned_ids == set(meeting_ids), (
        "Tập hợp bản ghi trả về không khớp với dữ liệu tạo!"
    )

    # 3. Tính ổn định: gọi lại trang 1 trả về chính xác thứ tự ban đầu
    res_p1_repeat = client_a.get(
        "/api/v1/meetings?page=1&page_size=5&sort_by=created_at&order=desc"
    )
    repeat_ids_p1 = [m["id"] for m in res_p1_repeat.json()["items"]]
    assert ids_p1 == repeat_ids_p1, "Thứ tự kết quả không ổn định qua các lần gọi!"


# ==============================================================================
# NHÓM 3: CORE RISK - BACKWARD COMPATIBILITY CHO CLIENT CŨ (SCHEMA INVARIANT)
# ==============================================================================


def test_core_risk_backward_compatibility_legacy_client(
    client_a: TestClient, test_db: Session, user_a: User
) -> None:
    """TC09: [Core Risk] Request theo chuẩn client cũ không chứa tham số mới.

    Phản hồi phải giữ nguyên cấu trúc MeetingListOut và không chứa bất kỳ trường lạ nào
    gây lỗi cho client dùng Pydantic với extra='forbid'.
    """
    m = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Cuộc họp tương thích client cũ",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(m)
    test_db.commit()

    # Client cũ chỉ gửi page và page_size
    res = client_a.get("/api/v1/meetings?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()

    # Xác thực với schema nghiêm ngặt MeetingListOut (extra='forbid')
    validated = MeetingListOut.model_validate(data)
    assert validated.page == 1
    assert validated.page_size == 10
    assert validated.total == 1
    assert len(validated.items) == 1

    # Kiểm tra không có trường lạ ở mức root JSON
    expected_keys = {"items", "page", "page_size", "total"}
    assert set(data.keys()) == expected_keys, (
        f"Phát hiện trường lạ phá vỡ schema: {set(data.keys()) - expected_keys}"
    )


# ==============================================================================
# NHÓM 4: TÌM KIẾM VÀ LỌC NÂNG CAO (SEARCH, SOURCE, DATE BOUNDARY)
# ==============================================================================


def test_search_keyword_sanitization_and_wildcard(
    client_a: TestClient, test_db: Session, user_a: User
) -> None:
    """TC10: Tìm kiếm từ khóa q: không phân biệt hoa thường, escape wildcard % và _."""
    m1 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Dự án 100%_Hoàn_Thành_Tiến_Độ",
        source="upload",
        status="ready",
        version=1,
    )
    m2 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Dự án 100xHoànxThànhxTiếnxĐộ",
        source="upload",
        status="ready",
        version=1,
    )
    m3 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Họp Planning Tuần SE2026",
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add_all([m1, m2, m3])
    test_db.commit()

    # 1. Tìm kiếm không phân biệt hoa thường và tự động strip khoảng trắng
    res_ci = client_a.get("/api/v1/meetings?q=  pLaNnInG  ")
    assert res_ci.status_code == 200
    assert res_ci.json()["total"] == 1
    assert res_ci.json()["items"][0]["id"] == m3.id

    # 2. Escape ký tự wildcard: '100%' phải chỉ khớp m1, không được hiểu '%' là đại diện nhiều ký tự
    res_wildcard = client_a.get("/api/v1/meetings?q=100%")
    assert res_wildcard.status_code == 200
    assert res_wildcard.json()["total"] == 1
    assert res_wildcard.json()["items"][0]["id"] == m1.id


def test_filter_by_source(client_a: TestClient, test_db: Session, user_a: User) -> None:
    """TC11: Lọc theo nguồn cuộc họp: source=upload hoặc source=recording."""
    m_up = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Bản ghi tải lên",
        source="upload",
        status="ready",
        version=1,
    )
    m_rec = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Bản ghi trực tiếp",
        source="recording",
        status="ready",
        version=1,
    )
    test_db.add_all([m_up, m_rec])
    test_db.commit()

    # Lọc recording
    res_rec = client_a.get("/api/v1/meetings?source=recording")
    assert res_rec.status_code == 200
    assert res_rec.json()["total"] == 1
    assert res_rec.json()["items"][0]["id"] == m_rec.id

    # Lọc upload
    res_up = client_a.get("/api/v1/meetings?source=upload")
    assert res_up.status_code == 200
    assert res_up.json()["total"] == 1
    assert res_up.json()["items"][0]["id"] == m_up.id


def test_filter_by_date_range_boundary(
    client_a: TestClient, test_db: Session, user_a: User
) -> None:
    """TC12: [BVA] Lọc theo khoảng ngày họp: from_date và to_date bao gồm cả ngày biên."""
    m1 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Họp ngày 01",
        source="upload",
        status="ready",
        meeting_date="2026-11-01",
        version=1,
    )
    m2 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Họp ngày 05",
        source="upload",
        status="ready",
        meeting_date="2026-11-05",
        version=1,
    )
    m3 = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_a.id,
        title="Họp ngày 10",
        source="upload",
        status="ready",
        meeting_date="2026-11-10",
        version=1,
    )
    test_db.add_all([m1, m2, m3])
    test_db.commit()

    # 1. Khoảng bao trùm m1 và m2 (2026-11-01 đến 2026-11-05)
    res_range = client_a.get("/api/v1/meetings?from_date=2026-11-01&to_date=2026-11-05")
    assert res_range.status_code == 200
    assert res_range.json()["total"] == 2
    ids = [m["id"] for m in res_range.json()["items"]]
    assert m1.id in ids
    assert m2.id in ids
    assert m3.id not in ids

    # 2. Biên trùng ngày: from_date=2026-11-05 và to_date=2026-11-05
    res_exact = client_a.get("/api/v1/meetings?from_date=2026-11-05&to_date=2026-11-05")
    assert res_exact.status_code == 200
    assert res_exact.json()["total"] == 1
    assert res_exact.json()["items"][0]["id"] == m2.id


# ==============================================================================
# NHÓM 5: NEGATIVE TESTS & FAILURE-PATH TESTS
# ==============================================================================


def test_negative_invalid_date_format(client_a: TestClient) -> None:
    """TC13: [Negative Test] Định dạng ngày tháng không hợp lệ -> 422."""
    res = client_a.get("/api/v1/meetings?from_date=2026-99-99")
    assert res.status_code == 422

    res_str = client_a.get("/api/v1/meetings?to_date=invalid-date")
    assert res_str.status_code == 422


def test_negative_invalid_sort_by_column(client_a: TestClient) -> None:
    """TC14: [Negative Test] sort_by không nằm trong whitelist -> 422."""
    res = client_a.get("/api/v1/meetings?sort_by=password_hash;DROP+TABLE+meetings;")
    assert res.status_code == 422


def test_failure_path_owner_scoping_isolation(
    client_a: TestClient, client_b: TestClient, test_db: Session, user_a: User, user_b: User
) -> None:
    """TC15: [Failure-path / Security] Cô lập dữ liệu: User A không thấy cuộc họp của User B.

    Ngay cả khi User A tìm kiếm từ khóa khớp chính xác tiêu đề cuộc họp của User B.
    """
    secret_title = "Kế Hoạch Tuyệt Mật Của User B 987654321"
    m_b = Meeting(
        id=str(uuid.uuid4()),
        owner_id=user_b.id,
        title=secret_title,
        source="upload",
        status="ready",
        version=1,
    )
    test_db.add(m_b)
    test_db.commit()

    # User B tìm kiếm thấy
    res_b = client_b.get(f"/api/v1/meetings?q={secret_title}")
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 1
    assert res_b.json()["items"][0]["id"] == m_b.id

    # User A tìm kiếm hoàn toàn không thấy (total=0, items=[])
    res_a = client_a.get(f"/api/v1/meetings?q={secret_title}")
    assert res_a.status_code == 200
    assert res_a.json()["total"] == 0
    assert len(res_a.json()["items"]) == 0


def test_failure_path_unauthenticated(unauthed_client: TestClient) -> None:
    """TC16: [Failure-path / Auth] Gọi API không xác thực -> 401 Unauthorized."""
    res = unauthed_client.get("/api/v1/meetings")
    assert res.status_code == 401
