"""Kiểm tra `manifest.csv`: mỗi file đánh giá phải có nguồn, license, mục đích, consent.

uv run python datasets/check_manifest.py                 # chỉ kiểm nội dung
uv run python datasets/check_manifest.py --check-files   # kiểm thêm file có tồn tại
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.csv"

COLUMNS = [
    "id",
    "source",
    "kind",
    "split",
    "audio_path",
    "ref_path",
    "rttm_path",
    "duration_sec",
    "num_speakers",
    "language",
    "license",
    "purpose",
    "condition",
    "consent_ref",
    "ref_reviewed_by",
    "notes",
]
SOURCES = {"fleurs", "common_voice", "vivos", "internal", "musan"}
KINDS = {"read_speech", "meeting", "noisy_real", "noisy_synthetic"}
PURPOSES = {"wer", "der", "noisy", "rubric", "edge", "demo"}
NON_COMMERCIAL = {"CC-BY-NC-SA-4.0", "CC-BY-NC-4.0"}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
PRIVATE_DIR = "private"


def _relative(value: str) -> bool:
    p = PurePosixPath(value)
    return not p.is_absolute() and ".." not in p.parts


def check_rows(rows: list[dict[str, str]], base: Path | None = None) -> list[str]:
    """Trả về danh sách lỗi; rỗng là hợp lệ. Dòng đánh số theo file CSV (header là 1)."""
    errors: list[str] = []
    seen: set[str] = set()
    for n, row in enumerate(rows, start=2):

        def err(msg: str, n: int = n) -> None:
            errors.append(f"dòng {n}: {msg}")

        rid = row.get("id", "")
        if not ID_PATTERN.match(rid):
            err(f"id không hợp lệ: {rid!r}")
        elif rid in seen:
            err(f"id trùng: {rid}")
        seen.add(rid)

        if row.get("source") not in SOURCES:
            err(f"source phải thuộc {sorted(SOURCES)}")
        if row.get("kind") not in KINDS:
            err(f"kind phải thuộc {sorted(KINDS)}")
        if not row.get("license"):
            err("thiếu license")
        if row.get("language") != "vi":
            err("language phải là vi")

        purposes = {p for p in row.get("purpose", "").split(";") if p}
        if not purposes or not purposes <= PURPOSES:
            err(f"purpose phải là các giá trị trong {sorted(PURPOSES)}, ngăn cách bằng ';'")
        if row.get("license") in NON_COMMERCIAL and "demo" in purposes:
            err("dữ liệu license phi thương mại không dùng cho demo công khai")

        if row.get("source") == "internal" and not row.get("consent_ref"):
            err("dữ liệu tự ghi phải có consent_ref")
        if row.get("source") == "internal":
            # Repo public: audio, transcript và RTTM của cuộc họp nội bộ không được commit.
            for col in ("audio_path", "ref_path", "rttm_path"):
                value = row.get(col, "")
                if value and PurePosixPath(value).parts[:1] != (PRIVATE_DIR,):
                    err(f"{col} của dữ liệu tự ghi phải nằm trong {PRIVATE_DIR}/ (không commit)")
        if row.get("kind") in {"noisy_real", "noisy_synthetic"} and not row.get("condition"):
            err("dữ liệu noisy phải ghi condition")

        try:
            if float(row.get("duration_sec", "")) <= 0:
                err("duration_sec phải > 0")
        except ValueError:
            err("duration_sec phải là số")
        speakers = row.get("num_speakers", "")
        if speakers and (not speakers.isdigit() or int(speakers) < 1):
            err("num_speakers phải là số nguyên >= 1")

        for col in ("audio_path", "ref_path", "rttm_path"):
            value = row.get(col, "")
            if not value:
                continue
            if not _relative(value):
                err(f"{col} phải là đường dẫn tương đối, không chứa '..'")
            elif base is not None and not (base / value).exists():
                err(f"{col} không tồn tại: {value}")
        if not row.get("audio_path"):
            err("thiếu audio_path")
        if row.get("ref_path") and not row.get("ref_reviewed_by"):
            err("transcript tham chiếu chưa được người thứ hai soát (ref_reviewed_by)")
    return errors


def read_manifest(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra manifest.csv")
    parser.add_argument("manifest", nargs="?", type=Path, default=MANIFEST)
    parser.add_argument("--check-files", action="store_true", help="kiểm file có tồn tại")
    args = parser.parse_args(argv)

    header, rows = read_manifest(args.manifest)
    if header != COLUMNS:
        print(f"header phải đúng thứ tự: {','.join(COLUMNS)}", file=sys.stderr)
        return 1
    errors = check_rows(rows, args.manifest.parent if args.check_files else None)
    for e in errors:
        print(e, file=sys.stderr)
    print(f"{len(rows)} dòng, {len(errors)} lỗi")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
