"""Độ đồng thuận giữa hai người chấm tóm tắt theo `rubric.md` (AI-14).

    uv run python summary_rubric/agreement.py summary_rubric/ratings.csv --tag summary-v1

- Input: `ratings.csv`, mỗi dòng là điểm 1–5 của một người chấm cho một cuộc họp.
- Mỗi cuộc họp cần đúng 2 người chấm. Cuộc họp chỉ có 1 người chấm thì bị bỏ khỏi phép tính
  và được liệt kê riêng, để con số không đẹp giả.
- Output: `summary_rubric/results/<YYYY-MM-DD>_<tag>/` gồm `agreement.json` và `report.md`.
  Theo từng tiêu chí: tỉ lệ cặp điểm trùng, tỉ lệ lệch không quá 1 điểm, độ lệch tuyệt đối
  trung bình, điểm trung bình của từng người chấm. Không chép `notes` sang kết quả.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CRITERIA = ("coverage", "faithfulness", "decisions", "action_items", "evidence", "language")
COLUMNS = ["meeting_id", "rater", "prompt_version", *CRITERIA, "notes"]
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class InputError(Exception):
    pass


@dataclass(frozen=True)
class Rating:
    meeting_id: str
    rater: str
    prompt_version: str
    scores: dict[str, int]


@dataclass(frozen=True)
class CriterionAgreement:
    criterion: str
    pairs: int
    exact: float
    within_one: float
    mean_abs_diff: float
    mean_by_rater: dict[str, float]


def load_ratings(path: Path) -> list[Rating]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise InputError(f"header phải là: {','.join(COLUMNS)}")
        ratings, seen = [], set()
        for n, row in enumerate(reader, start=2):
            key = (row["meeting_id"].strip(), row["rater"].strip())
            if not all(key):
                raise InputError(f"dòng {n}: thiếu meeting_id hoặc rater")
            if key in seen:
                raise InputError(f"dòng {n}: {key[1]} đã chấm {key[0]} ở dòng trước")
            seen.add(key)
            scores = {}
            for c in CRITERIA:
                value = row[c].strip()
                if value not in {"1", "2", "3", "4", "5"}:
                    raise InputError(f"dòng {n}: {c} phải là số nguyên 1–5, nhận {value!r}")
                scores[c] = int(value)
            ratings.append(Rating(*key, row["prompt_version"].strip(), scores))
    return ratings


def pair_up(ratings: list[Rating]) -> tuple[list[tuple[Rating, Rating]], list[str]]:
    """Cặp điểm theo cuộc họp, và danh sách cuộc họp chưa đủ 2 người chấm."""
    by_meeting: dict[str, list[Rating]] = defaultdict(list)
    for r in ratings:
        by_meeting[r.meeting_id].append(r)
    pairs, incomplete = [], []
    for meeting_id in sorted(by_meeting):
        group = sorted(by_meeting[meeting_id], key=lambda r: r.rater)
        if len(group) == 2:
            pairs.append((group[0], group[1]))
        elif len(group) == 1:
            incomplete.append(meeting_id)
        else:
            raise InputError(f"{meeting_id} có {len(group)} người chấm, cần đúng 2")
    return pairs, incomplete


def agreement(pairs: list[tuple[Rating, Rating]]) -> list[CriterionAgreement]:
    if not pairs:
        raise InputError("chưa có cuộc họp nào đủ 2 người chấm")
    result = []
    for c in CRITERIA:
        diffs = [abs(a.scores[c] - b.scores[c]) for a, b in pairs]
        by_rater: dict[str, list[int]] = defaultdict(list)
        for pair in pairs:
            for r in pair:
                by_rater[r.rater].append(r.scores[c])
        result.append(
            CriterionAgreement(
                criterion=c,
                pairs=len(pairs),
                exact=round(sum(d == 0 for d in diffs) / len(diffs), 3),
                within_one=round(sum(d <= 1 for d in diffs) / len(diffs), 3),
                mean_abs_diff=round(sum(diffs) / len(diffs), 3),
                mean_by_rater={k: round(sum(v) / len(v), 2) for k, v in sorted(by_rater.items())},
            )
        )
    return result


def report(rows: list[CriterionAgreement], incomplete: list[str], versions: list[str]) -> str:
    raters = sorted({k for r in rows for k in r.mean_by_rater})
    head = " | ".join(f"TB {k}" for k in raters)
    lines = [
        "# Độ đồng thuận chấm tóm tắt",
        "",
        f"- Số cuộc họp đủ 2 người chấm: {rows[0].pairs}",
        f"- Prompt: {', '.join(versions) or 'không ghi'}",
        f"- Chưa đủ người chấm (không tính): {', '.join(incomplete) or 'không có'}",
        "",
        f"| Tiêu chí | Trùng điểm | Lệch ≤ 1 | Lệch TB | {head} |",
        "|---|---|---|---|" + "---|" * len(raters),
    ]
    for r in rows:
        means = " | ".join(f"{r.mean_by_rater.get(k, float('nan')):.2f}" for k in raters)
        flag = " ⚠" if r.within_one < 0.8 else ""
        lines.append(
            f"| `{r.criterion}`{flag} | {r.exact:.0%} | {r.within_one:.0%} | "
            f"{r.mean_abs_diff:.2f} | {means} |"
        )
    lines += [
        "",
        "⚠: lệch ≤ 1 dưới 80 %, cần thống nhất lại cách hiểu tiêu chí (xem `rubric.md`).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("ratings", type=Path)
    parser.add_argument("--tag", required=True, help="ví dụ summary-v1")
    parser.add_argument("--date", type=date.fromisoformat, default=None, help="mặc định hôm nay")
    parser.add_argument("--out", type=Path, help="mặc định results/<date>_<tag>")
    parser.add_argument("--force", action="store_true", help="ghi đè thư mục kết quả đã có")
    args = parser.parse_args(argv)
    if not TAG_PATTERN.match(args.tag):
        parser.error("tag chỉ gồm chữ thường, số, '.', '_', '-'")
    out = args.out or RESULTS / f"{(args.date or date.today()).isoformat()}_{args.tag}"
    if out.exists() and not args.force:
        parser.error(f"{out} đã tồn tại (dùng --force để ghi đè)")

    try:
        ratings = load_ratings(args.ratings)
        pairs, incomplete = pair_up(ratings)
        rows = agreement(pairs)
    except InputError as e:
        print(f"lỗi: {e}", file=sys.stderr)
        return 2

    versions = sorted({r.prompt_version for r in ratings if r.prompt_version})
    out.mkdir(parents=True, exist_ok=True)
    data = {
        "pairs": len(pairs),
        "incomplete": incomplete,
        "prompt_versions": versions,
        "criteria": [asdict(r) for r in rows],
    }
    (out / "agreement.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    (out / "report.md").write_text(report(rows, incomplete, versions), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
