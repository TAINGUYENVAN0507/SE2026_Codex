"""Test agreement.py với bộ điểm tự tạo, kết quả tính tay."""

import csv
import json
from pathlib import Path

import agreement
import pytest

SAME = {"faithfulness": 5, "decisions": 5, "action_items": 5, "evidence": 5, "language": 5}


def write(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=agreement.COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({"prompt_version": "summary-v1", "notes": "", **SAME, **row})
    return path


@pytest.fixture
def ratings(tmp_path) -> Path:
    return write(
        tmp_path / "ratings.csv",
        [
            # coverage lệch 0, 2, 1 điểm.
            {"meeting_id": "meet-001", "rater": "A", "coverage": 4},
            {"meeting_id": "meet-001", "rater": "B", "coverage": 4},
            {"meeting_id": "meet-002", "rater": "A", "coverage": 3},
            {"meeting_id": "meet-002", "rater": "B", "coverage": 5, "notes": "CANARY_7f3a"},
            {"meeting_id": "meet-003", "rater": "B", "coverage": 3},
            {"meeting_id": "meet-003", "rater": "A", "coverage": 2},
            # Chỉ A chấm: không tính.
            {"meeting_id": "meet-004", "rater": "A", "coverage": 1},
        ],
    )


def test_agreement_matches_hand_computed_values(ratings):
    pairs, incomplete = agreement.pair_up(agreement.load_ratings(ratings))
    assert incomplete == ["meet-004"]
    rows = {r.criterion: r for r in agreement.agreement(pairs)}
    cov = rows["coverage"]
    assert (cov.pairs, cov.exact, cov.within_one, cov.mean_abs_diff) == (3, 0.333, 0.667, 1.0)
    assert cov.mean_by_rater == {"A": 3.0, "B": 4.0}
    assert (rows["faithfulness"].exact, rows["faithfulness"].mean_abs_diff) == (1.0, 0.0)


def test_cli_writes_report_without_notes(ratings, tmp_path):
    out = tmp_path / "out"
    assert agreement.main([str(ratings), "--tag", "summary-v1", "--out", str(out)]) == 0
    data = json.loads((out / "agreement.json").read_text())
    assert data["pairs"] == 3 and data["incomplete"] == ["meet-004"]
    report = (out / "report.md").read_text()
    assert "| `coverage` ⚠ | 33% | 67% | 1.00 | 3.00 | 4.00 |" in report
    assert "| `faithfulness` | 100% | 100% | 0.00 | 5.00 | 5.00 |" in report
    for name in ("agreement.json", "report.md"):
        assert "CANARY_7f3a" not in (out / name).read_text()


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([{"meeting_id": "m", "rater": "A", "coverage": 6}], "1–5"),
        ([{"meeting_id": "m", "rater": "A", "coverage": ""}], "1–5"),
        (
            [
                {"meeting_id": "m", "rater": "A", "coverage": 3},
                {"meeting_id": "m", "rater": "A", "coverage": 4},
            ],
            "đã chấm",
        ),
        ([{"meeting_id": "", "rater": "A", "coverage": 3}], "thiếu"),
    ],
)
def test_invalid_rows_are_rejected(tmp_path, rows, message):
    path = write(tmp_path / "r.csv", rows)
    with pytest.raises(agreement.InputError, match=message):
        agreement.load_ratings(path)


def test_three_raters_for_one_meeting_is_an_error(tmp_path):
    rows = [{"meeting_id": "m", "rater": r, "coverage": 3} for r in ("A", "B", "C")]
    with pytest.raises(agreement.InputError, match="cần đúng 2"):
        agreement.pair_up(agreement.load_ratings(write(tmp_path / "r.csv", rows)))


def test_no_complete_pair_is_an_error(tmp_path):
    path = write(tmp_path / "r.csv", [{"meeting_id": "m", "rater": "A", "coverage": 3}])
    pairs, _ = agreement.pair_up(agreement.load_ratings(path))
    with pytest.raises(agreement.InputError, match="chưa có"):
        agreement.agreement(pairs)


def test_header_must_match(tmp_path):
    path = tmp_path / "r.csv"
    path.write_text("meeting_id,rater,score\nm,A,3\n", encoding="utf-8")
    with pytest.raises(agreement.InputError, match="header"):
        agreement.load_ratings(path)


def test_template_has_the_expected_header():
    template = Path(agreement.__file__).parent / "ratings.csv"
    assert template.read_text(encoding="utf-8").splitlines() == [",".join(agreement.COLUMNS)]
