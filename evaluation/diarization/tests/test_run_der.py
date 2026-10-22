import csv
import json
from pathlib import Path

import check_manifest as cm
import pytest
import run_der


def rttm(path: Path, turns) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            f"SPEAKER x 1 {s:.3f} {e - s:.3f} <NA> <NA> {spk} <NA> <NA>\n" for s, e, spk in turns
        ),
        encoding="utf-8",
    )
    return path


REF = [(0.0, 10.0, "spk1"), (10.0, 20.0, "spk2")]


@pytest.fixture
def setup(tmp_path):
    base = tmp_path / "datasets"
    rttm(base / "private/refs/meet-001.rttm", REF)
    row = dict.fromkeys(cm.COLUMNS, "")
    row.update(
        id="meet-001",
        source="internal",
        kind="meeting",
        split="pilot",
        audio_path="private/audio/meet-001.webm",
        rttm_path="private/refs/meet-001.rttm",
        duration_sec="20.0",
        num_speakers="2",
        language="vi",
        license="internal-consent",
        purpose="wer;der",
        consent_ref="CF-2026-001",
    )
    other = {**row, "id": "meet-002", "purpose": "wer", "rttm_path": ""}
    manifest = base / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cm.COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows([row, other])
    return manifest, tmp_path / "hyp"


def run(setup, tmp_path, *extra, out="out"):
    manifest, hyp = setup
    argv = [
        "--hyp-dir",
        str(hyp),
        "--tag",
        "t1",
        "--manifest",
        str(manifest),
        "--out",
        str(tmp_path / out),
    ]
    return run_der.main([*argv, *extra])


def summary(tmp_path, out="out"):
    return json.loads((tmp_path / out / "summary.json").read_text(encoding="utf-8"))["groups"]


def test_read_rttm_skips_comments_and_rejects_garbage(tmp_path):
    p = tmp_path / "a.rttm"
    p.write_text(
        "# chú thích\n\n"
        "SPEAKER x 1 1.0 2.5 <NA> <NA> A <NA> <NA>\n"
        "SPEAKER x 1 4 0 <NA> <NA> B <NA> <NA>\n"
    )
    assert run_der.read_rttm(p) == [(1.0, 3.5, "A")]
    p.write_text("not rttm at all\n")
    with pytest.raises(run_der.common.InputError):
        run_der.read_rttm(p)


def test_perfect_hypothesis_has_zero_der(setup, tmp_path):
    rttm(setup[1] / "meet-001.rttm", [(0, 10, "x"), (10, 20, "y")])  # nhãn khác tên vẫn đúng
    assert run(setup, tmp_path, "--collar", "0") == 0
    g = summary(tmp_path)["meeting"]
    assert (g["samples"], g["der"], g["mean_abs_speaker_count_error"]) == (1, 0.0, 0.0)


def test_confusion_without_collar(setup, tmp_path):
    rttm(setup[1] / "meet-001.rttm", [(0, 12, "x"), (12, 20, "y")])
    assert run(setup, tmp_path, "--collar", "0") == 0
    g = summary(tmp_path)["meeting"]
    assert (g["total"], g["confusion"], g["missed"], g["false_alarm"]) == (20.0, 2.0, 0.0, 0.0)
    assert g["der"] == pytest.approx(0.1)


def test_default_collar_removes_quarter_second_around_boundaries(setup, tmp_path):
    rttm(setup[1] / "meet-001.rttm", [(0, 12, "x"), (12, 20, "y")])
    assert run(setup, tmp_path) == 0
    # Collar 0.25 s bỏ 0.125 s mỗi phía của ranh giới 0, 10, 20 s: tổng còn 19.5 s,
    # confusion còn 10.125-12 = 1.875 s.
    assert summary(tmp_path)["meeting"]["der"] == pytest.approx(1.875 / 19.5, abs=1e-6)


def test_overlap_counted_or_skipped(tmp_path, setup):
    manifest, hyp = setup
    rttm(manifest.parent / "private/refs/meet-001.rttm", [(0, 12, "spk1"), (10, 20, "spk2")])
    rttm(hyp / "meet-001.rttm", [(0, 11, "x"), (11, 20, "y")])  # bỏ sót người nói chen
    assert run(setup, tmp_path, "--collar", "0") == 0
    g = summary(tmp_path)["meeting"]
    assert g["der"] > 0
    assert g["mean_sample_der_skip_overlap"] == 0.0


def test_missing_hypothesis(setup, tmp_path, capsys):
    assert run(setup, tmp_path) == 1
    assert "meet-001" in capsys.readouterr().err
    assert run(setup, tmp_path, "--allow-missing", "--collar", "0") == 0
    g = summary(tmp_path)["meeting"]
    assert (g["missing"], g["missed"], g["der"]) == (1, 20.0, 1.0)


def test_outputs_are_reproducible_and_contain_no_text(setup, tmp_path):
    rttm(setup[1] / "meet-001.rttm", [(0, 12, "x"), (12, 20, "y")])
    assert run(setup, tmp_path, out="a") == 0
    assert run(setup, tmp_path, out="b") == 0
    for name in ("per_sample.csv", "summary.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    rows = list(csv.DictReader((tmp_path / "a/per_sample.csv").open(encoding="utf-8")))
    assert [(r["id"], r["ref_speakers"], r["hyp_speakers"]) for r in rows] == [
        ("meet-001", "2", "2")
    ]
    assert "# Kết quả DER: t1" in (tmp_path / "a/report.md").read_text(encoding="utf-8")


def test_no_der_rows_is_an_error(tmp_path, capsys):
    base = tmp_path / "datasets"
    base.mkdir()
    (base / "manifest.csv").write_text(",".join(cm.COLUMNS) + "\n", encoding="utf-8")
    argv = ["--hyp-dir", str(tmp_path), "--tag", "t", "--manifest", str(base / "manifest.csv")]
    assert run_der.main([*argv, "--out", str(tmp_path / "o")]) == 1
    assert "purpose der" in capsys.readouterr().err
