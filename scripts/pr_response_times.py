#!/usr/bin/env python3
# ruff: noqa: E501
"""Thời gian phản hồi PR, đọc từ GitHub (RE-018: 20 giờ, AD-018: 18 giờ).

Chạy ở thư mục gốc repo, cần `gh` đã đăng nhập:

    python3 scripts/pr_response_times.py --out docs/evidence/pr-response-times.md

"Phản hồi" là review hoặc comment đầu tiên của một tài khoản KHÔNG phải tác giả PR.
Tác giả tự review, tự comment hay tự merge không tính. Review ghi bằng file trong repo
(`docs/*/reviews/PR-<số>-*.md`) không thấy được từ API: bảng ghi riêng ở cột cuối, kèm thời
điểm commit đầu tiên của file, và không tính vào tóm tắt.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path

QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes {
        number title state isDraft createdAt mergedAt closedAt
        author { login }
        mergedBy { login }
        reviews(first: 50) { nodes { author { login } submittedAt state } }
        comments(first: 50) { nodes { author { login } createdAt } }
      }
    }
  }
}
"""

# Vai trò trong nhóm (tasks/ROADMAP.md); login GitHub đã công khai trong repo.
ROLES = {"vantuong": "A", "mactuongmvt": "A", "minhquangha": "B", "TAINGUYENVAN0507": "C"}
LIMITS = (18, 20)


def ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def hours(a: datetime, b: datetime) -> float:
    return round((b - a).total_seconds() / 3600, 1)


def fetch(repo: str) -> list[dict]:
    owner, name = repo.split("/")
    out = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)["data"]["repository"]["pullRequests"]["nodes"]


def first_response(pr: dict) -> tuple[datetime, str, str] | None:
    author = (pr.get("author") or {}).get("login")
    events = [
        (ts(r["submittedAt"]), r["author"]["login"], f"review {r['state'].lower()}")
        for r in pr["reviews"]["nodes"]
        if r.get("author") and r["author"]["login"] != author and r.get("submittedAt")
    ] + [
        (ts(c["createdAt"]), c["author"]["login"], "comment")
        for c in pr["comments"]["nodes"]
        if c.get("author") and c["author"]["login"] != author
    ]
    return min(events) if events else None


def repo_reviews() -> dict[int, list[str]]:
    """PR số -> ['<file> (commit <thời điểm UTC>)'] cho review ghi bằng file trong repo."""
    found: dict[int, list[str]] = {}
    for f in sorted(Path("docs").glob("*/reviews/PR-*.md")):
        m = re.match(r"PR-(\d+)-", f.name)
        if not m:
            continue
        first = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--", str(f)],
            capture_output=True,
            text=True,
        ).stdout.split()
        when = f"{ts(first[-1]).astimezone(UTC):%Y-%m-%d %H:%M}" if first else "chưa commit"
        found.setdefault(int(m.group(1)), []).append(f"`{f}` (commit {when})")
    return found


def who(login: str | None) -> str:
    return f"{ROLES.get(login or '', '?')} (`{login}`)" if login else "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="TAINGUYENVAN0507/SE2026_Codex")
    ap.add_argument("--out")
    ap.add_argument(
        "--since",
        default="2026-11-06",
        help="ngày nhóm bắt đầu áp dụng quy định review trong 18 giờ (tasks/ROADMAP.md)",
    )
    args = ap.parse_args()
    since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)

    in_repo = repo_reviews()
    rows = []
    groups = {"all": {"n": 0, "waits": [], "merged_first": []}}
    groups["since"] = {"n": 0, "waits": [], "merged_first": []}
    for pr in fetch(args.repo):
        opened, merged = ts(pr["createdAt"]), ts(pr["mergedAt"])
        resp = first_response(pr)
        mine = [groups["all"]] + ([groups["since"]] if opened >= since else [])
        for g in mine:
            g["n"] += 1
        if resp:
            when, by, kind = resp
            wait = hours(opened, when)
            for g in mine:
                g["waits"].append(wait)
            resp_txt = f"{wait} giờ, {kind}, {who(by)}"
        else:
            when = None
            resp_txt = "không có"
        if merged and (when is None or when > merged):
            for g in mine:
                g["merged_first"].append(pr["number"])
        state = (
            f"merge sau {hours(opened, merged)} giờ, bởi {who(pr['mergedBy']['login'])}"
            if merged
            else (
                "đang mở" + (" (draft)" if pr["isDraft"] else "")
                if pr["state"] == "OPEN"
                else "đóng, không merge"
            )
        )
        flag = "" if not merged or (when and when <= merged) else " **merge trước khi có phản hồi**"
        note = "; ".join(in_repo.get(pr["number"], []))
        rows.append(
            f"| #{pr['number']} | {who(pr['author']['login'])} | {opened:%Y-%m-%d %H:%M} "
            f"| {resp_txt} | {state}{flag} | {note} |"
        )

    def summary(g: dict) -> list[str]:
        waits = g["waits"]
        within = {h: sum(w <= h for w in waits) for h in LIMITS}
        return [
            f"- PR có phản hồi từ người khác: {len(waits)}/{g['n']}.",
            f"- Trong số đó, phản hồi trong 18 giờ (AD-018): {within[18]}/{len(waits)}; "
            f"trong 20 giờ (RE-018): {within[20]}/{len(waits)}.",
            f"- Trung vị thời gian tới phản hồi đầu tiên: {statistics.median(waits) if waits else '–'} giờ; "
            f"lâu nhất: {max(waits) if waits else '–'} giờ.",
            f"- Merge khi chưa có phản hồi của người khác: "
            f"{', '.join(f'#{n}' for n in g['merged_first']) or 'không có'}.",
        ]

    now = datetime.now(UTC)
    md = [
        "# Thời gian phản hồi PR",
        "",
        f"Sinh bằng `python3 scripts/pr_response_times.py` lúc {now:%Y-%m-%d %H:%M} UTC, từ GitHub API của `{args.repo}`.",
        "",
        "Phản hồi = review hoặc comment đầu tiên của tài khoản **không phải** tác giả. Tự review, tự merge không tính.",
        "Review ghi bằng file trong repo (`docs/*/reviews/`) không thấy được từ API: ghi ở cột cuối, không tính vào tóm tắt.",
        "",
        f"## Từ khi áp dụng quy định review trong 18 giờ ({args.since})",
        "",
        *summary(groups["since"]),
        "",
        "## Toàn bộ PR",
        "",
        *summary(groups["all"]),
        "",
        "## Từng PR (giờ UTC)",
        "",
        "| PR | Tác giả | Mở lúc | Phản hồi đầu tiên của người khác | Kết thúc | Review ghi trong repo |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]
    text = "\n".join(md)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
