import json

import pytest
from jsonschema import Draft202012Validator

from meeting_pipeline import contracts_export as ce

CONTRACTS = ce.REPO_ROOT / "contracts"
pytestmark = pytest.mark.skipif(not CONTRACTS.exists(), reason="chạy ngoài repo")


def test_committed_contracts_match_code():
    stale = ce.check(ce.REPO_ROOT)
    assert stale == [], (
        f"contract lệch với code: {stale}. Chạy: uv run python -m meeting_pipeline.contracts_export"
    )


def test_schemas_are_valid_json_schema():
    for name, _, _ in ce.SCHEMAS:
        schema = json.loads((ce.REPO_ROOT / ce.SCHEMA_DIR / f"{name}.schema.json").read_text())
        Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    "fixture", sorted(p.stem for p in (ce.REPO_ROOT / ce.FIXTURE_DIR).glob("*.json"))
)
def test_fixture_matches_json_schema_and_pydantic(fixture):
    name = ce.fixture_schema_name(fixture)
    schema = json.loads((ce.REPO_ROOT / ce.SCHEMA_DIR / f"{name}.schema.json").read_text())
    instance = json.loads((ce.REPO_ROOT / ce.FIXTURE_DIR / f"{fixture}.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(instance))
    assert errors == [], [e.message for e in errors]
    model = next(m for n, m, _ in ce.SCHEMAS if n == name)
    model.model_validate(instance)


def test_output_schemas_require_every_field():
    schema = json.loads((ce.REPO_ROOT / ce.SCHEMA_DIR / "transcript.schema.json").read_text())
    assert set(schema["required"]) == set(schema["properties"])


def test_fixture_schema_name():
    assert ce.fixture_schema_name("summary_disabled") == "summary"
    assert ce.fixture_schema_name("diarization") == "diarization"
    with pytest.raises(KeyError):
        ce.fixture_schema_name("unknown")


def test_write_then_check_in_empty_root(tmp_path):
    written = ce.write(tmp_path)
    assert len(written) == len(ce.render())
    assert ce.check(tmp_path) == []
    assert ce.write(tmp_path) == []
    assert ce.main(["--root", str(tmp_path), "--check"]) == 0
    (tmp_path / ce.SCHEMA_DIR / "vad.schema.json").write_text("{}")
    assert ce.main(["--root", str(tmp_path), "--check"]) == 1
