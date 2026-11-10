"""Thử mutation trong working tree cô lập; luôn hoàn nguyên file trước khi thoát."""

import argparse
import difflib
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/vt017/mutations"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    service = Path("app/services/meeting_search.py")
    original = service.read_bytes()
    source = original.decode("utf-8")
    experiments = [
        (
            "authorization",
            source.replace(
                "base_query = select(Meeting).where(Meeting.owner_id == owner_id)",
                "base_query = (select(Meeting) if q and q.strip() else "
                "select(Meeting).where(Meeting.owner_id == owner_id))",
            ),
            "tests/api/test_meeting_search_pagination.py",
            "test_failure_path_owner_scoping_isolation",
        ),
        (
            "tiebreaker",
            source.replace(
                "primary_column.asc(), Meeting.id.asc()", "primary_column.asc()"
            ).replace("primary_column.desc(), Meeting.id.desc()", "primary_column.desc()"),
            "tests/api/test_meeting_search_pagination.py",
            "test_stable_result_ordering_deterministic_tiebreaker",
        ),
    ]
    results = []
    try:
        for name, mutated, file, selector in experiments:
            if mutated == source:
                raise RuntimeError("Không tìm thấy mục tiêu mutation.")
            service.write_bytes(mutated.encode("utf-8"))
            difference = "".join(
                difflib.unified_diff(
                    source.splitlines(True),
                    mutated.splitlines(True),
                    fromfile="clean",
                    tofile=name,
                    n=0,
                )
            )
            (args.output / f"{name}.diff").write_text(
                difference.replace("\r\n", "\n"), encoding="utf-8"
            )
            command = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                file,
                "-k",
                selector,
                "-q",
                "-p",
                "no:cacheprovider",
                "--tb=short",
            ]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            run = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
            )
            output = run.stdout + run.stderr
            (args.output / f"{name}.log").write_text(output, encoding="utf-8")
            results.append(
                {
                    "mutation": name,
                    "exit_code": run.returncode,
                    "killed": run.returncode == 1 and "1 failed" in output,
                    "test": selector,
                }
            )
    finally:
        service.write_bytes(original)
    (args.output / "summary.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    return 0 if all(result["killed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
