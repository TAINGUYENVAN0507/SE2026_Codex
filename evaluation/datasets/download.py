"""Tải dữ liệu đánh giá có kiểm tra sha256.

    uv run python datasets/download.py --list
    uv run python datasets/download.py fleurs_vi_test_tsv fleurs_vi_test_audio

File được tải vào `datasets/raw/<source_id>/` (đã nằm trong .gitignore). Nếu checksum
không khớp với `sources.json`, file bị xóa và script trả về mã lỗi 1.

Thêm nguồn mới: ghi entry vào `sources.json` với `"sha256": null`, chạy với `--pin`
để ghi checksum của lần tải đầu, rồi commit `sources.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources.json"
RAW = HERE / "raw"
CHUNK = 1 << 20


class ChecksumError(Exception):
    pass


def load_sources(path: Path = SOURCES) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _filename(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def fetch(url: str, dest: Path) -> str:
    """Tải `url` về `dest` (qua file .part). Trả về sha256 của nội dung."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, part.open("wb") as out:
            while chunk := resp.read(CHUNK):
                h.update(chunk)
                out.write(chunk)
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)
    return h.hexdigest()


def extract(archive: Path, into: Path) -> None:
    with tarfile.open(archive) as tar:
        # filter="data" chặn đường dẫn tuyệt đối, "..", symlink ra ngoài thư mục đích.
        tar.extractall(into, filter="data")


def download(
    source_id: str,
    sources: dict[str, dict],
    raw_dir: Path = RAW,
    pin: bool = False,
) -> Path:
    entry = sources[source_id]
    dest = raw_dir / source_id / _filename(entry["url"])
    expected = entry.get("sha256")

    if dest.exists() and expected and sha256_file(dest) == expected:
        print(f"{source_id}: đã có, checksum khớp")
    else:
        print(f"{source_id}: đang tải {entry['url']}")
        actual = fetch(entry["url"], dest)
        if expected is None:
            if not pin:
                dest.unlink()
                raise ChecksumError(f"{source_id}: chưa có sha256, chạy lại với --pin")
            entry["sha256"] = actual
            print(f"{source_id}: đã ghi sha256 {actual}")
        elif actual != expected:
            dest.unlink()
            raise ChecksumError(f"{source_id}: sha256 {actual} khác {expected}")

    if entry.get("extract"):
        extract(dest, dest.parent)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tải dữ liệu đánh giá có kiểm tra sha256")
    parser.add_argument("source_ids", nargs="*")
    parser.add_argument("--list", action="store_true", help="liệt kê các nguồn")
    parser.add_argument("--pin", action="store_true", help="ghi sha256 cho nguồn chưa có")
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    args = parser.parse_args(argv)

    sources = load_sources(args.sources)
    if args.list or not args.source_ids:
        for sid, entry in sources.items():
            size = entry.get("size_bytes")
            size_txt = f"{size / 1e6:.1f} MB" if size else "?"
            print(f"{sid:28} {entry['license']:14} {size_txt:>10}  {entry['description']}")
        return 0

    unknown = [s for s in args.source_ids if s not in sources]
    if unknown:
        print(f"không có nguồn: {', '.join(unknown)}", file=sys.stderr)
        return 2

    try:
        for sid in args.source_ids:
            download(sid, sources, args.raw_dir, pin=args.pin)
    except ChecksumError as e:
        print(f"lỗi: {e}", file=sys.stderr)
        return 1
    finally:
        if args.pin:
            args.sources.write_text(
                json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
