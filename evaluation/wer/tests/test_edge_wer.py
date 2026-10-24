"""Test edge_wer.py: nhiều case cùng một clip, WER tính tay."""

import csv
import json
from pathlib import Path

import check_manifest as cm
import edge_wer
import pytest
import run_wer


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    base = tmp_path / "datasets"
    (base / "refs").mkdir(parents=True)
    (base / "refs" / "fleurs-1.txt").write_text("giao thông gần như không bị gián đoạn\n")
    row = dict.fromkeys(cm.COLUMNS, "")
    row.update(
        id="fleurs-1",
        source="fleurs",
        kind="read_speech",
        split="test",
        audio_path="raw/fleurs-1.wav",
        ref_path="refs/fleurs-1.txt",
        duration_sec="5.0",
        language="vi",
        license="CC-BY-4.0",
        purpose="wer",
        ref_reviewed_by="FLEURS",
    )
    path = base / "manifest.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cm.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    return path


def write_cases(path: Path, items: list[tuple[str, str]]) -> Path:
    lines = [json.dumps({"case": c, "id": "fleurs-1", "text": t}) for c, t in items]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_each_case_scored_against_the_same_reference(tmp_path, manifest):
    hyp = write_cases(
        tmp_path / "edge.jsonl",
        [
            ("clean", "Giao thông gần như không bị gián đoạn."),
            # 8 từ: 1 thay thế (gần -> gặp), 1 xóa (bị): 2/8.
            ("noisy", "giao thông gặp như không gián đoạn"),
        ],
    )
    out = edge_wer.table(edge_wer.load_cases(hyp), manifest).splitlines()
    assert out[2].startswith("| `clean` | 0.000 |")
    assert out[3].startswith("| `noisy` | 0.250 |")
    assert out[3].endswith("| 1/1/0 |")


def test_unknown_id_is_an_error(tmp_path, manifest):
    hyp = tmp_path / "edge.jsonl"
    hyp.write_text(json.dumps({"case": "x", "id": "nope", "text": "a"}) + "\n")
    with pytest.raises(run_wer.InputError):
        edge_wer.table(edge_wer.load_cases(hyp), manifest)


def test_missing_field_is_an_error(tmp_path):
    hyp = tmp_path / "edge.jsonl"
    hyp.write_text(json.dumps({"case": "x", "text": "a"}) + "\n")
    with pytest.raises(run_wer.InputError):
        edge_wer.load_cases(hyp)
