"""Test run_noisy.py với transcriber giả: chọn clip, WER theo điều kiện, report không có text."""

import csv
import json
import shutil
from pathlib import Path

import make_noisy as mn
import numpy as np
import pytest
import run_noisy as rn

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")
REF = "giao thông gần như không bị gián đoạn"


def row(cid: str, **kw) -> dict[str, str]:
    base = {"id": cid, "source": "fleurs", "purpose": "wer", "ref_path": f"refs/{cid}.txt"}
    return {**base, **kw}


def test_select_clips_filters_and_sorts():
    rows = [
        row("fleurs-3"),
        row("fleurs-1"),
        row("meet-001", source="internal"),
        row("fleurs-2", purpose="der"),
        row("fleurs-4", ref_path=""),
    ]
    assert [r["id"] for r in rn.select_clips(rows, 2)] == ["fleurs-1", "fleurs-3"]
    with pytest.raises(ValueError, match="cần 3"):
        rn.select_clips(rows, 3)


def test_babble_paths_skip_evaluated_clips(tmp_path):
    for name in ("a", "b", "c", "d"):
        (tmp_path / f"{name}.wav").write_bytes(b"")
    assert [p.stem for p in rn.babble_paths(tmp_path, {"b"}, 2)] == ["a", "c"]
    with pytest.raises(ValueError):
        rn.babble_paths(tmp_path, set(), 5)


CONDITIONS = [
    {"id": "clean", "type": "clean"},
    {"id": "pink0", "type": "noise", "color": "pink", "snr_db": 0},
]


def lines_for(texts: dict[tuple[str, str], tuple[str, str]]) -> list[dict]:
    return [
        {
            "id": cid,
            "condition": cond,
            "status": st,
            "snr_measured_db": 0.1 if cond != "clean" else None,
            "text": t,
        }
        for (cid, cond), (st, t) in texts.items()
    ]


def test_per_condition_is_corpus_wer_with_delta_and_no_speech():
    refs = {"c1": REF, "c2": REF}
    lines = lines_for(
        {
            ("c1", "clean"): ("ok", REF),
            ("c2", "clean"): ("ok", REF),
            # 8 + 8 từ: c1 thay 2 từ, c2 bị VAD từ chối (xóa 8 từ) → 10/16.
            ("c1", "pink0"): ("ok", "giao thông gặp như không bị gián đoạn nhé"),
            ("c2", "pink0"): ("no_speech", ""),
        }
    )
    rows = rn.per_condition(lines, refs, CONDITIONS)
    clean, noisy = rows
    assert (clean["wer"], clean["delta_wer_vs_clean"], clean["no_speech"]) == (0.0, 0.0, 0)
    assert noisy["wer"] == pytest.approx(10 / 16, abs=1e-4)
    assert noisy["delta_wer_vs_clean"] == noisy["wer"]
    assert (noisy["no_speech"], noisy["snr_target_db"], noisy["snr_measured_db"]) == (1, 0, 0.1)
    assert noisy["source"] == "synthetic"


def test_missing_condition_is_an_error():
    lines = lines_for({("c1", "clean"): ("ok", REF)})
    with pytest.raises(ValueError, match="pink0"):
        rn.per_condition(lines, {"c1": REF}, CONDITIONS)


@needs_ffmpeg
def test_transcribe_suite_runs_every_condition(tmp_path, monkeypatch):
    t = np.arange(16000 * 2) / 16000
    clip_dir = tmp_path / "datasets" / "raw"
    clip_dir.mkdir(parents=True)
    mn.write_wav(clip_dir / "c1.wav", 0.3 * np.sin(2 * np.pi * 220 * t))
    monkeypatch.setattr(rn, "DATASETS", tmp_path / "datasets")
    conditions = [
        mn.Condition("clean", "clean"),
        mn.Condition("pink5", "noise", {"color": "pink", "snr_db": 5}),
    ]
    seen = []

    def fake(path: Path):
        seen.append(path.name)
        return "ok", "xin chào"

    lines = rn.transcribe_suite(
        [{"id": "c1", "audio_path": "raw/c1.wav"}], conditions, 1, [], fake, tmp_path / "work"
    )
    assert seen == ["c1__clean.wav", "c1__pink5.wav"]
    assert [ln["condition"] for ln in lines] == ["clean", "pink5"]
    assert lines[0]["snr_measured_db"] is None
    assert lines[1]["snr_measured_db"] == pytest.approx(5, abs=0.5)


def test_score_writes_results_without_text(tmp_path):
    datasets = tmp_path / "datasets"
    (datasets / "refs").mkdir(parents=True)
    (datasets / "refs" / "c1.txt").write_text(REF + "\n", encoding="utf-8")
    manifest = datasets / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "source", "purpose", "ref_path"])
        writer.writeheader()
        writer.writerow(row("c1"))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    canary = "CANARYTOKEN"  # không có chữ số: normalizer giữ thành 1 từ
    lines = lines_for({("c1", "clean"): ("ok", REF), ("c1", "pink0"): ("ok", f"{REF} {canary}")})
    (run_dir / "hyp.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    meta = {"tag": "t", "seed": 1, "clips": ["c1"], "conditions": CONDITIONS, "asr": "fake"}
    (run_dir / "meta.json").write_text(json.dumps(meta))

    out = tmp_path / "out"
    argv = ["score", str(run_dir), "--manifest", str(manifest), "--out", str(out)]
    assert rn.main(argv) == 0
    with (out / "per_condition.csv").open(encoding="utf-8") as f:
        result = list(csv.DictReader(f))
    assert [r["condition"] for r in result] == ["clean", "pink0"]
    assert float(result[1]["wer"]) == pytest.approx(1 / 8)
    for name in ("per_condition.csv", "report.md", "env.json"):
        assert canary not in (out / name).read_text(encoding="utf-8")
    assert "| `pink0` |" in (out / "report.md").read_text(encoding="utf-8")
    assert rn.main(argv) == 2  # đã tồn tại, không ghi đè
