import csv
import json
from pathlib import Path

import check_manifest as cm
import pytest
import run_asr


def row(rid: str, **overrides) -> dict[str, str]:
    r = dict.fromkeys(cm.COLUMNS, "")
    r.update(
        id=rid,
        source="fleurs",
        kind="read_speech",
        split="test",
        audio_path=f"raw/{rid}.wav",
        ref_path=f"refs/{rid}.txt",
        duration_sec="4.0",
        language="vi",
        license="CC-BY-4.0",
        purpose="wer",
        ref_reviewed_by="FLEURS",
    )
    r.update(overrides)
    return r


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    d = tmp_path / "datasets"
    d.mkdir()
    rows = [row("fleurs-2"), row("fleurs-1"), row("fleurs-3", purpose="der", ref_path="")]
    path = d / "manifest.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cm.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def fake_transcriber(texts: dict[str, str], fail: set[str] = frozenset()):
    calls = {}

    def factory(model, device, compute_type, params):
        calls.update(model=model, device=device, compute_type=compute_type, params=params)

        def transcribe(path: Path):
            if path.stem in fail:
                raise RuntimeError("CUDA error")
            return f"  {texts[path.stem]} ", 4.0

        return transcribe, 1.25

    return factory, calls


def test_select_rows_keeps_wer_rows_sorted():
    rows = [row("b"), row("a"), row("c", purpose="der"), row("d", kind="meeting")]
    assert [r["id"] for r in run_asr.select_rows(rows)] == ["a", "b", "d"]
    assert [r["id"] for r in run_asr.select_rows(rows, kind="read_speech")] == ["a", "b"]


def test_main_writes_hypotheses_and_meta(tmp_path, manifest):
    factory, calls = fake_transcriber({"fleurs-1": "xin chào", "fleurs-2": "tạm biệt"})
    argv = ["--model", "small", "--tag", "t1", "--manifest", str(manifest)]
    assert run_asr.main([*argv, "--device", "cpu", "--out", str(tmp_path / "out")], factory) == 0

    lines = [json.loads(x) for x in (tmp_path / "out" / "hyp.jsonl").read_text().splitlines()]
    assert [(x["id"], x["text"], x["audio_sec"]) for x in lines] == [
        ("fleurs-1", "xin chào", 4.0),
        ("fleurs-2", "tạm biệt", 4.0),
    ]
    meta = json.loads((tmp_path / "out" / "meta.json").read_text())
    assert (meta["model"], meta["compute_type"], meta["device"]) == ("small", "int8", "cpu")
    assert (meta["samples"], meta["errors"], meta["audio_sec"]) == (2, 0, 8.0)
    assert meta["model_load_sec"] == 1.25
    assert meta["rtf"] == pytest.approx(meta["proc_sec"] / 8.0, abs=1e-3)
    assert meta["params"]["condition_on_previous_text"] is False
    assert meta["params"]["language"] == "vi"
    assert calls["params"].vad_filter is True


def test_failed_file_is_recorded_not_skipped(tmp_path, manifest):
    factory, _ = fake_transcriber({"fleurs-1": "xin chào"}, fail={"fleurs-2"})
    argv = ["--model", "small", "--tag", "t1", "--manifest", str(manifest)]
    assert run_asr.main([*argv, "--device", "cpu", "--out", str(tmp_path / "out")], factory) == 0
    lines = [json.loads(x) for x in (tmp_path / "out" / "hyp.jsonl").read_text().splitlines()]
    assert lines[1] == {**lines[1], "id": "fleurs-2", "text": "", "error": "RuntimeError"}
    assert json.loads((tmp_path / "out" / "meta.json").read_text())["errors"] == 1


def test_limit_no_vad_and_overwrite_guard(tmp_path, manifest, capsys):
    factory, calls = fake_transcriber({"fleurs-1": "a", "fleurs-2": "b"})
    argv = ["--model", "m", "--tag", "t1", "--manifest", str(manifest), "--device", "cpu"]
    out = ["--out", str(tmp_path / "out")]
    assert run_asr.main([*argv, *out, "--limit", "1", "--no-vad"], factory) == 0
    assert len((tmp_path / "out" / "hyp.jsonl").read_text().splitlines()) == 1
    assert calls["params"].vad_filter is False
    assert run_asr.main([*argv, *out], factory) == 1
    assert "--force" in capsys.readouterr().err


def test_bad_tag_is_rejected(manifest):
    factory, _ = fake_transcriber({})
    assert (
        run_asr.main(["--model", "m", "--tag", "Bad Tag", "--manifest", str(manifest)], factory)
        == 1
    )
