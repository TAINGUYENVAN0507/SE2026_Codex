import csv

import check_manifest as cm
import import_fleurs as fl


def tsv_line(sid: str, name: str, text: str, samples: int = 80000) -> str:
    return "\t".join([sid, name, text, text.lower(), "x", str(samples), "MALE"])


def write_tsv(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def datasets_dir(tmp_path):
    d = tmp_path / "datasets"
    d.mkdir()
    with (d / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow(cm.COLUMNS)
    return d


def sample_clips(tmp_path):
    lines = [
        tsv_line(str(1000 + s), f"{s}{k}.wav", f"Câu số {s}.") for s in range(10) for k in range(3)
    ]
    return fl.read_tsv(write_tsv(tmp_path / "test.tsv", lines))


def test_select_one_clip_per_sentence_and_deterministic(tmp_path):
    clips = sample_clips(tmp_path)
    a = fl.select(clips, 5, seed=1)
    assert len(a) == 5
    assert len({c.sentence_id for c in a}) == 5
    assert a == fl.select(clips, 5, seed=1)
    assert a != fl.select(clips, 5, seed=2)
    assert [c.id for c in a] == sorted(c.id for c in a)


def test_select_caps_at_number_of_sentences(tmp_path):
    assert len(fl.select(sample_clips(tmp_path), 99, seed=1)) == 10


def test_import_writes_valid_manifest_and_refs(tmp_path):
    d = datasets_dir(tmp_path)
    clips = fl.select(sample_clips(tmp_path), 4, seed=1)
    assert fl.import_clips(clips, d) == 4

    header, rows = cm.read_manifest(d / "manifest.csv")
    assert header == cm.COLUMNS
    assert cm.check_rows(rows) == []
    row = rows[0]
    assert row["id"] == clips[0].id
    assert row["audio_path"] == f"raw/fleurs_vi_test_audio/test/{clips[0].file_name}"
    assert row["duration_sec"] == "5.000"
    assert (d / row["ref_path"]).read_text(encoding="utf-8") == clips[0].raw_transcription + "\n"


def test_import_is_idempotent(tmp_path):
    d = datasets_dir(tmp_path)
    clips = fl.select(sample_clips(tmp_path), 4, seed=1)
    fl.import_clips(clips, d)
    assert fl.import_clips(clips, d) == 0
    _, rows = cm.read_manifest(d / "manifest.csv")
    assert len(rows) == 4


def test_cli_requires_tsv(tmp_path, capsys):
    assert fl.main(["--tsv", str(tmp_path / "missing.tsv"), "--datasets-dir", str(tmp_path)]) == 1
    assert "download.py" in capsys.readouterr().err
