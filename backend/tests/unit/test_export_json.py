"""Golden tests của JSON export và contract, không cần database."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.services.export import MeetingExport, export_schema, to_json

FIXTURES = Path(__file__).parents[1] / "fixtures/export"
ROOT = Path(__file__).parents[3]


def source() -> MeetingExport:
    """Đọc dữ liệu do nhóm tự viết trong fixture test."""
    return MeetingExport.model_validate_json((FIXTURES / "source.json").read_text(encoding="utf-8"))


def test_export_json_golden_and_deterministic() -> None:
    meeting = source()
    before = meeting.model_dump()
    first = to_json(meeting)
    assert (
        first
        == to_json(meeting)
        == (FIXTURES / "current.json").read_text(encoding="utf-8").encode()
    )
    assert "Đề án" in first.decode()
    assert meeting.model_dump() == before


@pytest.mark.parametrize("variant", ["current", "ai_original"])
def test_export_json_validates_against_generated_contract(variant: str) -> None:
    schema = json.loads((ROOT / "contracts/export.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(to_json(source(), variant)))
    assert schema == export_schema()


def test_export_ai_original_does_not_leak_current_edits() -> None:
    output = json.loads(to_json(source(), "ai_original"))
    assert output["segments"][0]["text"] == "Nội dung gốc."
    assert output["segments"][0]["speaker_id"] is None
    assert output["speakers"][0]["name"] == "Speaker 1"
    assert output["summary"]["overview"] == "Tổng quan AI."
    assert [item["description"] for item in output["action_items"]] == ["Công việc AI"]
    assert output["action_items"][0]["status"] == "open"


def test_export_schema_check_detects_drift(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.services.export", "--check"], capture_output=True, check=False
    )
    assert result.returncode == 0
    wrong = tmp_path / "schema.json"
    wrong.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "app.services.export", "--check", "--output", str(wrong)],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1


def test_export_rejects_invalid_times() -> None:
    values = source().model_dump()
    values["segments"][0]["end_sec"] = 0
    with pytest.raises(ValidationError):
        MeetingExport.model_validate(values)
