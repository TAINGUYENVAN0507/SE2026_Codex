#!/usr/bin/env python3
"""Ma trận mutation (VT-018): mỗi test giết được mutant nào.

    python scripts/mutation_matrix.py docs/evidence/vt-018/ai-tests/mutants.json \
        --cwd backend --tests tests/unit/test_vt018_ai_raw.py --out <file.json>

Với mỗi mutant trong file JSON (`file`, `old`, `new`, đường dẫn tính từ `--cwd`): thay `old` bằng
`new`, chạy pytest trên `--tests`, đọc junit XML để biết test nào fail, rồi LUÔN khôi phục file
gốc. Test đã fail khi chưa có mutant (baseline) thì không được tính là giết mutant.
Từ chối chạy khi file đích có thay đổi chưa commit, hoặc khi `old` không xuất hiện đúng 1 lần.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def run_tests(cwd: Path, tests: list[str]) -> dict[str, str]:
    """Chạy pytest, trả về {test id: 'passed' | 'failed'}."""
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "junit.xml"
        cmd = ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml_path}"]
        subprocess.run(
            [*cmd, *tests],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if not xml_path.exists():
            raise RuntimeError("pytest không sinh junit XML (lỗi import?)")
        results: dict[str, str] = {}
        for case in ET.parse(xml_path).iter("testcase"):
            name = f"{case.get('classname')}::{case.get('name')}"
            bad = case.find("failure") is not None or case.find("error") is not None
            results[name] = "failed" if bad else "passed"
        return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--tests", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cwd = Path(args.cwd).resolve()
    mutants = json.loads(Path(args.spec).read_text(encoding="utf-8"))["mutants"]

    for m in mutants:
        path = cwd / m["file"]
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)], capture_output=True, text=True
        ).stdout.strip()
        if dirty:
            print(f"Từ chối: {path} có thay đổi chưa commit", file=sys.stderr)
            return 2
        count = path.read_text(encoding="utf-8").count(m["old"])
        if count != 1:
            print(f"{m['id']}: `old` xuất hiện {count} lần trong {m['file']}", file=sys.stderr)
            return 2

    baseline = run_tests(cwd, args.tests)
    base_failed = sorted(t for t, r in baseline.items() if r == "failed")
    print(f"baseline: {len(baseline)} test, {len(base_failed)} fail sẵn: {base_failed}")

    kills: dict[str, list[str]] = {}
    for m in mutants:
        path = cwd / m["file"]
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(original.replace(m["old"], m["new"], 1), encoding="utf-8")
            results = run_tests(cwd, args.tests)
        finally:
            path.write_text(original, encoding="utf-8")
        killers = sorted(
            t for t, r in results.items() if r == "failed" and baseline.get(t) == "passed"
        )
        kills[m["id"]] = killers
        print(f"{m['id']} {'KILLED' if killers else 'SURVIVED'} ({len(killers)} test) {m['what']}")

    Path(args.out).write_text(
        json.dumps(
            {
                "tests": args.tests,
                "baseline": baseline,
                "baseline_failed": base_failed,
                "mutants": [{**m, "killed_by": kills[m["id"]]} for m in mutants],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
