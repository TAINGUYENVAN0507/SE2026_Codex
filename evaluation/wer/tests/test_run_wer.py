import csv
import hashlib
import json
from pathlib import Path

import check_manifest as cm
import pytest
import run_wer

REFS = {
    "fleurs-1": "Mặt khác, băng và tuyết là hiện tượng bình thường.",
    "fleurs-2": "Giao thông gần như không bị gián đoạn.",
    "meet-001": "Ờ, anh Minh phụ trách phần upload, hạn thứ Sáu.",
}


def manifest_row(**overrides) -> dict[str, str]:
    row = dict.fromkeys(cm.COLUMNS, "")
    row.update(
        source="fleurs",
        kind="read_speech",
        split="test",
        duration_sec="5.0",
        language="vi",
        license="CC-BY-4.0",
        purpose="wer",
        ref_reviewed_by="FLEURS",
    )
    row.update(overrides)
    row["audio_path"] = row["audio_path"] or f"raw/{row['id']}.wav"
    return row


def write_manifest(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cm.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    base = tmp_path / "datasets"
    (base / "refs").mkdir(parents=True)
    for rid, text in REFS.items():
        (base / "refs" / f"{rid}.txt").write_text(text + "\n", encoding="utf-8")
    meeting = dict(
        source="internal",
        kind="meeting",
        split="pilot",
        license="internal-consent",
        consent_ref="CF-2026-001",
        num_speakers="3",
        ref_reviewed_by="B",
    )
    rows = [
        manifest_row(id="fleurs-1", ref_path="refs/fleurs-1.txt"),
        manifest_row(id="fleurs-2", ref_path="refs/fleurs-2.txt"),
        manifest_row(id="meet-001", ref_path="refs/meet-001.txt", purpose="wer;der", **meeting),
        # Không có purpose wer: không được chấm.
        manifest_row(id="meet-002", purpose="der", **{**meeting, "ref_reviewed_by": ""}),
    ]
    return write_manifest(base / "manifest.csv", rows)


def write_hyp(path: Path, items: dict[str, str]) -> Path:
    lines = [
        json.dumps({"id": k, "text": v, "proc_sec": 1.5}, ensure_ascii=False)
        for k, v in items.items()
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


HYPS = {
    "fleurs-1": "mặt khác băng và tuyết là hiện tượng bình thường",
    "fleurs-2": "giao thông gần như không bị dán đoạn",  # 1 lỗi thay thế / 8
    "meet-001": "anh minh phụ trách phần áp lốt hạn thứ sáu",  # 1 thay thế + 1 chèn / 9
}


def run(tmp_path: Path, manifest: Path, hyps: dict[str, str], *extra: str, out: str = "out"):
    hyp = write_hyp(tmp_path / "hyp.jsonl", hyps)
    argv = ["--hyp", str(hyp), "--tag", "t1", "--manifest", str(manifest)]
    return run_wer.main([*argv, "--out", str(tmp_path / out), *extra])


def read_per_sample(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_scores_each_kind_separately(tmp_path, manifest):
    assert run(tmp_path, manifest, HYPS) == 0
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    groups = summary["groups"]
    # Không có con số gộp chung giữa giọng đọc và cuộc họp.
    assert list(groups) == ["meeting", "read_speech"]

    meeting = groups["meeting"]
    assert (meeting["samples"], meeting["ref_tokens"]) == (1, 9)
    assert (meeting["substitutions"], meeting["insertions"], meeting["deletions"]) == (1, 1, 0)
    assert meeting["wer"] == pytest.approx(2 / 9, abs=1e-6)

    read = groups["read_speech"]
    assert (read["samples"], read["ref_tokens"], read["substitutions"]) == (2, 18, 1)
    assert read["wer"] == pytest.approx(1 / 18, abs=1e-6)
    assert read["mean_sample_wer"] == pytest.approx((0 + 1 / 8) / 2, abs=1e-6)
    assert read["missing"] == 0

    rows = read_per_sample(tmp_path / "out" / "per_sample.csv")
    assert [r["id"] for r in rows] == ["meet-001", "fleurs-1", "fleurs-2"]
    assert rows[0]["wer"] == "0.2222" and rows[0]["hyp_tokens"] == "10"
    assert rows[1]["wer"] == "0.0000"

    report = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "| `meeting` | 1 | 0 | 9 | 1 | 0 | 1 | 22.22 % |" in report


def test_rerun_gives_identical_files(tmp_path, manifest):
    assert run(tmp_path, manifest, HYPS, out="a") == 0
    assert run(tmp_path, manifest, HYPS, out="b") == 0
    for name in ("per_sample.csv", "summary.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_missing_hypothesis_is_rejected(tmp_path, manifest, capsys):
    hyps = {k: v for k, v in HYPS.items() if k != "meet-001"}
    assert run(tmp_path, manifest, hyps) == 1
    assert "meet-001" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_allow_missing_scores_as_empty_hypothesis(tmp_path, manifest):
    hyps = {k: v for k, v in HYPS.items() if k != "meet-001"}
    assert run(tmp_path, manifest, hyps, "--allow-missing") == 0
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    meeting = summary["groups"]["meeting"]
    assert (meeting["missing"], meeting["deletions"], meeting["wer"]) == (1, 9, 1.0)
    rows = read_per_sample(tmp_path / "out" / "per_sample.csv")
    assert rows[0]["id"] == "meet-001" and rows[0]["missing"] == "1"


def test_unknown_hypothesis_id_is_rejected(tmp_path, manifest, capsys):
    assert run(tmp_path, manifest, {**HYPS, "fleurs-999": "x"}) == 1
    assert "fleurs-999" in capsys.readouterr().err


def test_filtered_out_hypothesis_is_ignored(tmp_path, manifest):
    assert run(tmp_path, manifest, HYPS, "--kind", "read_speech") == 0
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert list(summary["groups"]) == ["read_speech"]
    assert summary["selection"]["kind"] == "read_speech"


def test_no_matching_row_is_rejected(tmp_path, manifest, capsys):
    assert run(tmp_path, manifest, HYPS, "--source", "vivos") == 1
    assert "không có dòng nào" in capsys.readouterr().err


@pytest.mark.parametrize(
    "content",
    [
        '{"id": "fleurs-1", "text": "a"}\n{"id": "fleurs-1", "text": "b"}\n',
        "không phải json\n",
        '{"id": "fleurs-1"}\n',
        '["fleurs-1", "a"]\n',
    ],
)
def test_bad_hypothesis_file_is_rejected(tmp_path, manifest, content):
    hyp = tmp_path / "hyp.jsonl"
    hyp.write_text(content, encoding="utf-8")
    argv = ["--hyp", str(hyp), "--tag", "t1", "--manifest", str(manifest)]
    assert run_wer.main([*argv, "--out", str(tmp_path / "out")]) == 1


def test_invalid_manifest_is_rejected(tmp_path, capsys):
    base = tmp_path / "datasets"
    base.mkdir()
    bad = manifest_row(
        id="meet-009", source="internal", kind="meeting", license="internal-consent"
    )  # thiếu consent_ref
    manifest = write_manifest(base / "manifest.csv", [bad])
    assert run(tmp_path, manifest, {}) == 1
    assert "consent_ref" in capsys.readouterr().err


def test_existing_results_are_not_overwritten(tmp_path, manifest, capsys):
    assert run(tmp_path, manifest, HYPS) == 0
    assert run(tmp_path, manifest, HYPS) == 1
    assert "--force" in capsys.readouterr().err
    assert run(tmp_path, manifest, HYPS, "--force") == 0


def test_default_output_dir_uses_date_and_tag(tmp_path, manifest, monkeypatch):
    monkeypatch.setattr(run_wer, "RESULTS", tmp_path / "results")
    hyp = write_hyp(tmp_path / "hyp.jsonl", HYPS)
    argv = ["--hyp", str(hyp), "--tag", "whisper-small", "--manifest", str(manifest)]
    assert run_wer.main([*argv, "--date", "2026-10-19"]) == 0
    assert (tmp_path / "results" / "2026-10-19_whisper-small" / "summary.json").exists()


def test_bad_tag_is_rejected(tmp_path, manifest):
    hyp = write_hyp(tmp_path / "hyp.jsonl", HYPS)
    assert run_wer.main(["--hyp", str(hyp), "--tag", "Bad Tag", "--manifest", str(manifest)]) == 1


def test_env_json_records_inputs(tmp_path, manifest):
    meta = tmp_path / "asr_meta.json"
    meta.write_text(json.dumps({"model": "fake-asr", "device": "cpu"}), encoding="utf-8")
    assert run(tmp_path, manifest, HYPS, "--asr-meta", str(meta)) == 0

    text = (tmp_path / "out" / "env.json").read_text(encoding="utf-8")
    env = json.loads(text)
    assert env["asr"] == {"model": "fake-asr", "device": "cpu"}
    hyp_sha = hashlib.sha256((tmp_path / "hyp.jsonl").read_bytes()).hexdigest()
    assert env["inputs"]["hyp"] == {"path": "hyp.jsonl", "sha256": hyp_sha}
    assert len(env["normalizer_sha256"]) == 64
    assert env["jiwer"].startswith("4.")
    # File ngoài repo chỉ ghi tên, không lộ đường dẫn tuyệt đối.
    assert str(tmp_path) not in text


def test_results_contain_no_transcript_text(tmp_path, manifest):
    assert run(tmp_path, manifest, HYPS) == 0
    for name in ("per_sample.csv", "summary.json", "env.json"):
        content = (tmp_path / "out" / name).read_text(encoding="utf-8").lower()
        for word in ("minh", "upload", "tuyết", "giao thông"):
            assert word not in content, (name, word)
