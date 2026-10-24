"""Chấm WER cho các case edge của pipeline: một clip, nhiều cách làm hỏng audio (AI-15).

    cd pipeline
    EDGE_HYP_OUT=/tmp/edge.jsonl uv run pytest -m model tests/edge/test_real_vad_asr.py
    cd ../evaluation && uv run python wer/edge_wer.py /tmp/edge.jsonl

- Input: JSONL, mỗi dòng `{"case": "...", "id": "<id trong manifest>", "text": "..."}`. Khác
  `run_wer.py`, nhiều dòng có thể cùng một `id`: cùng clip gốc, khác case.
- Output: bảng Markdown ra stdout (case, WER, CER, WER không dấu, S/D/I), theo thứ tự của file
  input. Bảng không chứa text, chỉ có số.

Chuẩn hóa và cách đếm lỗi giống `run_wer.py` (`metrics.score`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import run_wer
from metrics import score


def load_cases(path: Path) -> list[dict[str, str]]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not all(isinstance(item.get(k), str) for k in ("case", "id", "text")):
            raise run_wer.InputError(f"dòng {n}: cần các field case, id, text kiểu chuỗi")
        cases.append(item)
    return cases


def table(cases: list[dict[str, str]], manifest: Path) -> str:
    rows = {row["id"]: row for row in run_wer.load_manifest(manifest)}
    lines = [
        "| Case | WER | CER | WER không dấu | S/D/I |",
        "|---|---|---|---|---|",
    ]
    for item in cases:
        row = rows.get(item["id"])
        if row is None or not row["ref_path"]:
            raise run_wer.InputError(f"{item['id']} không có trong manifest hoặc thiếu reference")
        reference = (manifest.parent / row["ref_path"]).read_text(encoding="utf-8")
        s = score(reference, item["text"])
        w = s.words
        rates = (run_wer._rate(c.rate, 3) for c in (w, s.chars, s.words_nodiac))
        lines.append(
            f"| `{item['case']}` | {' | '.join(rates)} | "
            f"{w.substitutions}/{w.deletions}/{w.insertions} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("hyp", type=Path, help="file JSONL {case, id, text}")
    parser.add_argument("--manifest", type=Path, default=run_wer.MANIFEST)
    args = parser.parse_args(argv)
    try:
        print(table(load_cases(args.hyp), args.manifest))
    except run_wer.InputError as e:
        print(f"lỗi: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
