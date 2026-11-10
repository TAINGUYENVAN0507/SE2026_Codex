"""Bằng chứng bổ sung VT-017, dùng oracle hợp đồng được đóng băng ở baseline."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from app.db.models.meeting import Meeting
pytest_plugins = ("tests.api.test_meeting_search_pagination",)


def seed(db, user, count=4):
    """Tạo dữ liệu tổng hợp cố định; thứ tự chèn khác thứ tự ID."""
    records = []
    for i in reversed(range(count)):
        record = Meeting(
            id=str(uuid.UUID(int=i + 1)),
            owner_id=user.id,
            title="Planning 100%_Q\\A",
            source="recording" if i % 2 else "upload",
            status="ready" if i % 2 else "queued",
            meeting_date="2026-11-05",
            created_at=datetime(2026, 11, 5, 23, 59, tzinfo=UTC),
            updated_at=datetime(2026, 11, 5, 23, 59, tzinfo=UTC),
            version=1,
        )
        db.add(record)
        records.append(record)
    db.commit()
    return records


def legacy_schema():
    """Đọc schema độc lập với model hiện tại của server."""
    path = Path(__file__).parents[1] / "fixtures/vt017/legacy-response.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("size", [1, 2, 99, 100])
def test_bva_size_on_101_records(client_a, test_db, user_a, size):
    """TC17: Biên có dữ liệu thật, bao gồm ngay trong biên và sát biên trên."""
    seed(test_db, user_a, 101)
    response = client_a.get("/api/v1/meetings", params={"page_size": size})
    assert response.status_code == 200
    assert response.json()["total"] == 101
    assert len(response.json()["items"]) == size


def test_last_page_and_page_past_end(client_a, test_db, user_a):
    """TC18: Trang cuối còn hai mục; trang ngay sau rỗng nhưng total giữ nguyên."""
    seed(test_db, user_a, 101)
    for page, expected in [(2, 2), (3, 0)]:
        response = client_a.get("/api/v1/meetings", params={"page": page, "page_size": 99})
        assert response.status_code == 200
        assert response.json()["total"] == 101
        assert len(response.json()["items"]) == expected


@pytest.mark.parametrize("sort_by", ["created_at", "updated_at", "title", "meeting_date"])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_exact_tiebreaker_order(client_a, test_db, user_a, sort_by, order):
    """TC19: Oracle ID cố định bắt được thiếu tie-breaker và sai chiều sort."""
    records = seed(test_db, user_a)
    ids = []
    for page in [1, 2]:
        response = client_a.get(
            "/api/v1/meetings",
            params={"page": page, "page_size": 2, "sort_by": sort_by, "order": order},
        )
        assert response.status_code == 200
        ids.extend(item["id"] for item in response.json()["items"])
    assert ids == sorted((record.id for record in records), reverse=order == "desc")


@pytest.mark.parametrize("query", ["100%", "_Q", "Q\\A", "  pLaNnInG  "])
def test_literal_wildcards_and_whitespace(client_a, test_db, user_a, query):
    """TC20: Ký tự LIKE được hiểu theo nghĩa literal, trim và ASCII casefold."""
    records = seed(test_db, user_a, 1)
    test_db.add(
        Meeting(
            id=str(uuid.UUID(int=1000)),
            owner_id=user_a.id,
            title="other 100xxQxA",
            source="upload",
            status="ready",
            version=1,
        )
    )
    test_db.commit()
    response = client_a.get("/api/v1/meetings", params={"q": query})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [records[0].id]


@pytest.mark.parametrize("query", ["", "   "])
def test_blank_query_preserves_results(client_a, test_db, user_a, query):
    """TC21: Query trống tương đương không truyền bộ lọc từ khóa."""
    seed(test_db, user_a)
    actual = client_a.get("/api/v1/meetings", params={"q": query}).json()
    expected = client_a.get("/api/v1/meetings").json()
    assert actual == expected


def test_filters_intersect_and_legacy_client_reads_response(client_a, test_db, user_a):
    """TC22: Bộ lọc đồng thời lấy phép giao, response vẫn đọc bằng contract cũ."""
    records = seed(test_db, user_a)
    response = client_a.get(
        "/api/v1/meetings",
        params={
            "source": "recording",
            "status": "ready",
            "q": "planning",
            "from_date": "2026-11-05",
            "to_date": "2026-11-05",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert {item["id"] for item in data["items"]} == {
        record.id for record in records if record.source == "recording"
    }
    jsonschema.validate(data, legacy_schema())


@pytest.mark.parametrize(
    "date_value, count", [("2026-11-04", 0), ("2026-11-05", 1), ("2026-11-06", 0)]
)
def test_date_fallback_boundary(client_a, test_db, user_a, date_value, count):
    """TC23: Ngay dưới, tại và trên ngày fallback khi meeting_date null."""
    record = seed(test_db, user_a, 1)[0]
    record.meeting_date = None
    test_db.commit()
    response = client_a.get(
        "/api/v1/meetings", params={"from_date": date_value, "to_date": date_value}
    )
    assert response.status_code == 200
    assert response.json()["total"] == count


def test_reversed_date_range_is_empty(client_a, test_db, user_a):
    """TC24: Hai filter giao nhau thành tập rỗng khi khoảng ngày bị đảo."""
    seed(test_db, user_a)
    response = client_a.get(
        "/api/v1/meetings", params={"from_date": "2026-11-06", "to_date": "2026-11-04"}
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.parametrize("mutation", ["rename", "extra_root", "extra_item"])
def test_legacy_client_rejects_breaking_response(client_a, test_db, user_a, mutation):
    """TC25: Failure path riêng cho risk schema: oracle cũ từ chối payload hỏng."""
    seed(test_db, user_a, 1)
    data = client_a.get("/api/v1/meetings").json()
    jsonschema.validate(data, legacy_schema())
    if mutation == "rename":
        data["limit"] = data.pop("page_size")
    elif mutation == "extra_root":
        data["has_next"] = False
    else:
        data["items"][0]["unexpected"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, legacy_schema())


def test_metadata_api_journey(client_a, test_db, user_a):
    """TC26: Workflow API trên SQLite, không nhận là E2E trình duyệt/production."""
    records = seed(test_db, user_a)
    response = client_a.get("/api/v1/meetings", params={"source": "recording", "page_size": 1})
    assert response.status_code == 200
    assert response.json()["total"] == 2
    selected = response.json()["items"][0]["id"]
    assert selected in {record.id for record in records}
    detail = client_a.get(f"/api/v1/meetings/{selected}")
    assert detail.status_code == 200
    assert detail.json()["id"] == selected
