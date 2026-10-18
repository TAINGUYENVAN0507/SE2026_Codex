import csv

import check_manifest as cm
import pytest


def row(**overrides) -> dict[str, str]:
    base = dict.fromkeys(cm.COLUMNS, "")
    base.update(
        id="fleurs-1921-7702",
        source="fleurs",
        kind="read_speech",
        split="test",
        audio_path="raw/fleurs_vi_test_audio/test/7702.wav",
        duration_sec="9.84",
        language="vi",
        license="CC-BY-4.0",
        purpose="wer",
    )
    base.update(overrides)
    return base


def test_valid_rows_pass():
    internal = row(
        id="meet-001",
        source="internal",
        kind="meeting",
        license="internal-consent",
        purpose="wer;der;rubric",
        num_speakers="3",
        consent_ref="CF-2026-001",
        ref_path="refs/meet-001.txt",
        ref_reviewed_by="B",
    )
    assert cm.check_rows([row(), internal]) == []


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"id": "Bad ID"}, "id không hợp lệ"),
        ({"source": "youtube"}, "source"),
        ({"kind": "podcast"}, "kind"),
        ({"license": ""}, "license"),
        ({"language": "en"}, "language"),
        ({"purpose": "wer;train"}, "purpose"),
        ({"license": "CC-BY-NC-SA-4.0", "purpose": "wer;demo"}, "phi thương mại"),
        ({"source": "internal", "license": "internal-consent"}, "consent_ref"),
        ({"kind": "noisy_real"}, "condition"),
        ({"duration_sec": "abc"}, "duration_sec"),
        ({"duration_sec": "0"}, "duration_sec"),
        ({"num_speakers": "0"}, "num_speakers"),
        ({"audio_path": "/home/user/a.wav"}, "tương đối"),
        ({"audio_path": "../secret.wav"}, "tương đối"),
        ({"audio_path": ""}, "thiếu audio_path"),
        ({"ref_path": "refs/x.txt"}, "ref_reviewed_by"),
    ],
)
def test_invalid_rows(overrides, fragment):
    errors = cm.check_rows([row(**overrides)])
    assert any(fragment in e for e in errors), errors
    assert all(e.startswith("dòng 2:") for e in errors)


def test_duplicate_id():
    errors = cm.check_rows([row(), row()])
    assert errors == ["dòng 3: id trùng: fleurs-1921-7702"]


def test_check_files(tmp_path):
    (tmp_path / "raw").mkdir()
    errors = cm.check_rows([row(audio_path="raw/missing.wav")], base=tmp_path)
    assert any("không tồn tại" in e for e in errors)


def test_committed_manifest_is_valid():
    header, rows = cm.read_manifest(cm.MANIFEST)
    assert header == cm.COLUMNS
    assert cm.check_rows(rows) == []
    assert cm.main([]) == 0


def test_main_rejects_wrong_header(tmp_path):
    path = tmp_path / "m.csv"
    with path.open("w", newline="") as f:
        csv.writer(f).writerow(["id", "source"])
    assert cm.main([str(path)]) == 1
