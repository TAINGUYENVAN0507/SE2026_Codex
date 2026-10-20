import csv
import json
from pathlib import Path

import make_report
import pytest
from run_wer import PER_SAMPLE_COLUMNS


def group(**overrides) -> dict:
    g = {
        "samples": 2,
        "missing": 0,
        "ref_tokens": 20,
        "hits": 17,
        "substitutions": 2,
        "deletions": 1,
        "insertions": 1,
        "wer": 0.2,
        "mean_sample_wer": 0.25,
        "ref_chars": 90,
        "cer": 0.1,
        "wer_nodiac": 0.15,
    }
    g.update(overrides)
    return g


def sample(rid: str, kind: str = "read_speech", errors: int = 0, missing: int = 0) -> dict:
    row = dict.fromkeys(PER_SAMPLE_COLUMNS, "0")
    row.update(
        id=rid,
        source="fleurs",
        kind=kind,
        split="test",
        ref_tokens="10",
        substitutions=str(errors),
        wer=f"{errors / 10:.4f}",
        missing=str(missing),
    )
    return row


SUMMARY = {
    "tag": "whisper-small-int8",
    "selection": {"source": None, "kind": None, "split": "test", "allow_missing": False},
    "groups": {"meeting": group(wer=0.31234), "read_speech": group()},
}
ENV = {
    "created_at": "2026-10-19T04:20:11Z",
    "git": {"sha": "f4d716b89f87491b7567f997898265077d241150", "dirty": False},
    "python": "3.13.9",
    "jiwer": "4.0.0",
    "normalizer_sha256": "b5db08c5fab9c3b4fd04988829fe508fa86c9821a1ec43833e7196ccf3928cbe",
    "inputs": {
        "manifest": {"path": "evaluation/datasets/manifest.csv", "sha256": "d6d7e57b3096c0ca"},
        "hyp": {"path": "hyp.jsonl", "sha256": "b4dfaf9dfbfc2e69"},
    },
    "asr": {"model": "small", "compute_type": "int8", "gpu": "GTX 1650 Ti | 4 GB"},
}


def test_report_has_one_row_per_kind_and_no_combined_number():
    report = make_report.render(SUMMARY, [sample("a")], ENV)
    assert "# Kết quả WER: whisper-small-int8" in report
    table = report.split("## Kết quả theo loại dữ liệu")[1].split("\n\n")[1].splitlines()
    assert table[2:] == [
        "| `meeting` | 2 | 0 | 20 | 2 | 1 | 1 | 31.23 % | 25.00 % | 10.00 % | 15.00 % |",
        "| `read_speech` | 2 | 0 | 20 | 2 | 1 | 1 | 20.00 % | 25.00 % | 10.00 % | 15.00 % |",
    ]
    assert make_report.READ_SPEECH_NOTE in report


def test_report_lists_worst_samples_by_errors():
    rows = [sample(f"s{i:02d}", errors=i % 7) for i in range(15)]
    report = make_report.render(SUMMARY, rows, ENV)
    section = report.split("## 10 sample nhiều lỗi nhất")[1].split("## Môi trường")[0]
    listed = [line.split("`")[1] for line in section.splitlines() if line.startswith("| `")]
    assert listed[:4] == ["s06", "s13", "s05", "s12"]
    assert len(listed) == 10


def test_report_without_errors():
    report = make_report.render(SUMMARY, [sample("a"), sample("b")], ENV)
    assert "Không có sample nào có lỗi." in report


def test_report_warns_about_missing_and_dirty_runs():
    summary = {**SUMMARY, "groups": {"meeting": group(missing=1)}}
    env = {**ENV, "git": {**ENV["git"], "dirty": True}}
    report = make_report.render(summary, [sample("m1", "meeting", 10, missing=1)], env)
    assert "## Lưu ý" in report
    assert "1 sample thiếu hypothesis" in report
    assert "thay đổi chưa commit" in report
    assert "`m1` (thiếu hyp)" in report
    assert make_report.READ_SPEECH_NOTE not in report


def test_report_shows_environment_and_rerun_command():
    report = make_report.render(SUMMARY, [sample("a")], ENV)
    assert "| Git | `f4d716b89f87` |" in report
    assert "| ASR `gpu` | GTX 1650 Ti \\| 4 GB |" in report
    command = "uv run python wer/run_wer.py --hyp hyp.jsonl --tag whisper-small-int8 --split test"
    assert command in report


@pytest.mark.parametrize(
    ("manifest", "hyp", "expected"),
    [
        (
            "evaluation/datasets/manifest.csv",
            "evaluation/runs/hyp.jsonl",
            "--hyp runs/hyp.jsonl --tag whisper-small-int8 --split test",
        ),
        (
            "manifest.csv",
            "pipeline/out/hyp.jsonl",
            "--hyp ../pipeline/out/hyp.jsonl --tag whisper-small-int8 --manifest manifest.csv",
        ),
    ],
)
def test_rerun_command_paths_are_relative_to_evaluation(manifest, hyp, expected):
    inputs = {"manifest": {"path": manifest, "sha256": "x"}, "hyp": {"path": hyp, "sha256": "y"}}
    env = {**ENV, "inputs": inputs}
    assert expected in make_report.render(SUMMARY, [], env)


def test_report_without_asr_meta_or_env():
    no_asr = make_report.render(SUMMARY, [], {**ENV, "asr": None})
    assert "không có metadata" in no_asr
    assert "không có `env.json`" in make_report.render(SUMMARY, [], None)


def write_results(path: Path) -> Path:
    path.mkdir()
    (path / "summary.json").write_text(json.dumps(SUMMARY), encoding="utf-8")
    with (path / "per_sample.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PER_SAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerow(sample("a", errors=2))
    return path


def test_cli_writes_report(tmp_path, capsys):
    results = write_results(tmp_path / "r")
    assert make_report.main([str(results)]) == 0
    report = (results / "report.md").read_text(encoding="utf-8")
    assert "`a`" in report and "không có `env.json`" in report


@pytest.mark.parametrize("missing", ["summary.json", "per_sample.csv"])
def test_cli_fails_without_inputs(tmp_path, capsys, missing):
    results = write_results(tmp_path / "r")
    (results / missing).unlink()
    assert make_report.main([str(results)]) == 1
    assert "không sinh được report" in capsys.readouterr().err
