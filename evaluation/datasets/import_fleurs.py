"""Thêm một tập con cố định của FLEURS `vi_vn` test vào `manifest.csv` (AI-10, AI-01).

    uv run python datasets/download.py fleurs_vi_test_tsv
    uv run python datasets/import_fleurs.py --n 40

- Mỗi câu (cột id của FLEURS) chỉ lấy một clip, để tập con có nhiều câu khác nhau.
- Chọn bằng `random.Random(seed)` trên danh sách câu đã sắp xếp, nên cùng `--n` và
  `--seed` luôn cho cùng tập con.
- Transcript tham chiếu là cột `raw_transcription` (có dấu câu, có số), ghi vào
  `refs/<id>.txt`. FLEURS dùng license CC BY 4.0, được phép commit kèm ghi nguồn
  (`LICENSES.md`).
- Dòng đã có trong manifest thì giữ nguyên, không ghi trùng.

Audio không cần có sẵn để chạy script này; tải bằng `download.py fleurs_vi_test_audio`
trước khi chạy ASR.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import check_manifest as cm

HERE = Path(__file__).resolve().parent
TSV = HERE / "raw" / "fleurs_vi_test_tsv" / "test.tsv"
AUDIO_DIR = "raw/fleurs_vi_test_audio/test"
SAMPLE_RATE = 16000
GENDER = {"MALE": "nam", "FEMALE": "nữ"}


@dataclass(frozen=True)
class Clip:
    sentence_id: str
    file_name: str
    raw_transcription: str
    num_samples: int
    gender: str

    @property
    def id(self) -> str:
        return f"fleurs-{self.sentence_id}-{Path(self.file_name).stem}"


def read_tsv(path: Path) -> list[Clip]:
    clips = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            sentence_id, file_name, raw, _norm, _chars, num_samples, gender = row
            clips.append(Clip(sentence_id, file_name, raw, int(num_samples), gender))
    return clips


def select(clips: list[Clip], n: int, seed: int) -> list[Clip]:
    """Một clip cho mỗi câu, `n` câu chọn ngẫu nhiên có seed, sắp theo id."""
    by_sentence: dict[str, list[Clip]] = {}
    for clip in clips:
        by_sentence.setdefault(clip.sentence_id, []).append(clip)
    rng = random.Random(seed)
    sentences = sorted(by_sentence)
    chosen = rng.sample(sentences, min(n, len(sentences)))
    picked = [rng.choice(sorted(by_sentence[s], key=lambda c: c.file_name)) for s in chosen]
    return sorted(picked, key=lambda c: c.id)


def manifest_row(clip: Clip) -> dict[str, str]:
    row = dict.fromkeys(cm.COLUMNS, "")
    row.update(
        id=clip.id,
        source="fleurs",
        kind="read_speech",
        split="test",
        audio_path=f"{AUDIO_DIR}/{clip.file_name}",
        ref_path=f"refs/{clip.id}.txt",
        duration_sec=f"{clip.num_samples / SAMPLE_RATE:.3f}",
        num_speakers="1",
        language="vi",
        license="CC-BY-4.0",
        purpose="wer",
        ref_reviewed_by="FLEURS",
        notes=f"raw_transcription của FLEURS; giọng {GENDER.get(clip.gender, clip.gender)}",
    )
    return row


def import_clips(clips: list[Clip], datasets_dir: Path) -> int:
    """Ghi refs và thêm dòng vào manifest. Trả về số dòng mới."""
    manifest = datasets_dir / "manifest.csv"
    _, rows = cm.read_manifest(manifest)
    existing = {r["id"] for r in rows}
    new_rows = [manifest_row(c) for c in clips if c.id not in existing]
    for clip in clips:
        ref = datasets_dir / "refs" / f"{clip.id}.txt"
        if not ref.exists():
            ref.parent.mkdir(parents=True, exist_ok=True)
            ref.write_text(clip.raw_transcription + "\n", encoding="utf-8")
    with manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cm.COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows + new_rows)
    return len(new_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Thêm tập con FLEURS vi test vào manifest")
    parser.add_argument("--n", type=int, default=40, help="số câu (mỗi câu một clip)")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--tsv", type=Path, default=TSV)
    parser.add_argument("--datasets-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)

    if not args.tsv.exists():
        print(f"thiếu {args.tsv.name}: chạy download.py fleurs_vi_test_tsv", file=sys.stderr)
        return 1
    clips = select(read_tsv(args.tsv), args.n, args.seed)
    added = import_clips(clips, args.datasets_dir)
    minutes = sum(c.num_samples for c in clips) / SAMPLE_RATE / 60
    print(f"{len(clips)} clip ({minutes:.1f} phút), thêm {added} dòng mới vào manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
