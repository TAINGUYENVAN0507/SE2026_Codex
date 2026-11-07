#!/usr/bin/env python3
"""Mutation thủ công cho VT-018: đổi một toán tử `>` thành `>=` rồi xem test có bắt được không.

    python scripts/mutation_check.py backend/app/db/models/job.py 'max_attempts > self.attempt' \
        --cwd backend -- uv run pytest -q tests/unit/test_vt018_can_retry.py

Script sửa file tại chỗ, chạy lệnh test, rồi LUÔN khôi phục nội dung gốc (kể cả khi bị ngắt).
Kết quả: KILLED nếu test fail (mutant bị bắt), SURVIVED nếu test vẫn pass (thiếu test ở biên).
Chỉ dùng trên nhánh tạm hoặc working tree sạch: script từ chối chạy khi file có thay đổi chưa commit.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("snippet", help="đoạn code chứa đúng một toán tử `>` cần đổi, xuất hiện 1 lần")
    ap.add_argument("--cwd", default=".")
    argv = sys.argv[1:]
    if "--" not in argv:
        ap.error("thiếu `-- <lệnh test>`")
    split = argv.index("--")
    args = ap.parse_args(argv[:split])
    cmd = argv[split + 1 :]
    path = Path(args.file)

    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", str(path)], capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        print(f"Từ chối: {path} có thay đổi chưa commit", file=sys.stderr)
        return 2

    original = path.read_text(encoding="utf-8")
    if original.count(args.snippet) != 1 or " > " not in args.snippet:
        print("snippet phải xuất hiện đúng 1 lần và chứa ' > '", file=sys.stderr)
        return 2
    mutated = original.replace(args.snippet, args.snippet.replace(" > ", " >= ", 1))

    try:
        path.write_text(mutated, encoding="utf-8")
        print(f"MUTANT: {args.snippet!r} -> {args.snippet.replace(' > ', ' >= ', 1)!r}")
        result = subprocess.run(cmd, cwd=args.cwd, capture_output=True, text=True)
        tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
        print("\n".join(tail))
    finally:
        path.write_text(original, encoding="utf-8")

    verdict = "KILLED" if result.returncode != 0 else "SURVIVED"
    print(f"RESULT: {verdict} (exit {result.returncode})")
    return 0 if verdict == "KILLED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
