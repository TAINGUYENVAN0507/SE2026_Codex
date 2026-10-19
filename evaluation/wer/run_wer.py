"""Chấm WER cho output của một lần chạy ASR (AI-11).

    uv run python wer/run_wer.py --hyp hyp.jsonl --tag whisper-small-int8
    uv run python wer/run_wer.py --hyp hyp.jsonl --tag t1 --kind read_speech --allow-missing

- Reference: các dòng trong `datasets/manifest.csv` có purpose `wer` và có `ref_path`.
  Manifest phải hợp lệ theo `check_manifest.py` (nguồn, license, consent).
- Hypothesis: file JSONL, mỗi dòng `{"id": "<id trong manifest>", "text": "..."}`. Các
  field khác bị bỏ qua.
- Output: `wer/results/<YYYY-MM-DD>_<tag>/`
  - `per_sample.csv`: số lỗi S/D/I, WER, CER, WER không dấu của từng sample.
  - `summary.json`: WER cấp corpus theo từng `kind`. Không có con số gộp chung, vì giọng
    đọc (`read_speech`) không đại diện cho cuộc họp thật.
  - `env.json`: git SHA, version, sha256 của input và của normalizer, metadata của lần
    chạy ASR (`--asr-meta`).
  - `report.md`: bảng tóm tắt sinh từ ba file trên (`make_report.py`).

`per_sample.csv` và `summary.json` chỉ phụ thuộc input, nên chạy lại cho cùng byte.
Kết quả không chứa text của transcript: dữ liệu họp nội bộ chỉ dùng theo consent.

Sample có trong manifest nhưng thiếu hypothesis là lỗi, để WER không đẹp giả vì bỏ bớt
file khó. `--allow-missing` chấm sample đó như hypothesis rỗng (toàn lỗi xóa) và đếm
riêng trong cột `missing`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE.parent
REPO_ROOT = EVAL_ROOT.parent
# evaluation/ không phải package: thêm thư mục của các module dùng chung khi chạy script.
for _sub in ("normalizer", "datasets"):
    if str(EVAL_ROOT / _sub) not in sys.path:
        sys.path.insert(0, str(EVAL_ROOT / _sub))

import check_manifest  # noqa: E402
import make_report  # noqa: E402
import vi_normalize  # noqa: E402
from metrics import Counts, SampleScore, corpus, score  # noqa: E402

MANIFEST = EVAL_ROOT / "datasets" / "manifest.csv"
RESULTS = HERE / "results"
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

PER_SAMPLE_COLUMNS = [
    "id",
    "source",
    "kind",
    "split",
    "ref_tokens",
    "hyp_tokens",
    "hits",
    "substitutions",
    "deletions",
    "insertions",
    "wer",
    "ref_chars",
    "char_errors",
    "cer",
    "wer_nodiac",
    "missing",
]


class InputError(Exception):
    """Input không hợp lệ: script dừng với mã 1, không ghi kết quả nào."""


@dataclass(frozen=True)
class SampleResult:
    id: str
    source: str
    kind: str
    split: str
    score: SampleScore
    missing: bool


def load_hypotheses(path: Path) -> dict[str, str]:
    hyps: dict[str, str] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            raise InputError(f"{path.name} dòng {n}: không phải JSON") from None
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise InputError(f"{path.name} dòng {n}: cần object có field 'id' kiểu chuỗi")
        if not isinstance(item.get("text"), str):
            raise InputError(f"{path.name} dòng {n}: cần field 'text' kiểu chuỗi")
        if item["id"] in hyps:
            raise InputError(f"{path.name} dòng {n}: id trùng {item['id']}")
        hyps[item["id"]] = item["text"]
    return hyps


def load_manifest(path: Path) -> list[dict[str, str]]:
    header, rows = check_manifest.read_manifest(path)
    if header != check_manifest.COLUMNS:
        raise InputError(f"header của {path.name} không đúng, chạy check_manifest.py")
    errors = check_manifest.check_rows(rows)
    if errors:
        raise InputError(f"{path.name} không hợp lệ:\n" + "\n".join(errors))
    return rows


def select_rows(
    rows: list[dict[str, str]],
    source: str | None = None,
    kind: str | None = None,
    split: str | None = None,
) -> list[dict[str, str]]:
    """Dòng dùng để chấm WER: có purpose `wer`, có reference, khớp các bộ lọc."""
    selected = []
    for row in rows:
        if "wer" not in row["purpose"].split(";") or not row["ref_path"]:
            continue
        wanted = {"source": source, "kind": kind, "split": split}
        if any(value is not None and row[col] != value for col, value in wanted.items()):
            continue
        selected.append(row)
    return selected


def evaluate(
    rows: list[dict[str, str]],
    all_ids: set[str],
    hyps: dict[str, str],
    base: Path,
    allow_missing: bool = False,
) -> list[SampleResult]:
    unknown = sorted(set(hyps) - all_ids)
    if unknown:
        raise InputError(f"hypothesis có id không nằm trong manifest: {', '.join(unknown)}")
    missing = sorted(row["id"] for row in rows if row["id"] not in hyps)
    if missing and not allow_missing:
        raise InputError(
            f"{len(missing)} sample thiếu hypothesis: {', '.join(missing)} "
            "(dùng --allow-missing để chấm như hypothesis rỗng)"
        )

    results = []
    for row in rows:
        ref_file = base / row["ref_path"]
        try:
            reference = ref_file.read_text(encoding="utf-8")
        except OSError:
            raise InputError(f"không đọc được reference {row['ref_path']}") from None
        results.append(
            SampleResult(
                id=row["id"],
                source=row["source"],
                kind=row["kind"],
                split=row["split"],
                score=score(reference, hyps.get(row["id"], "")),
                missing=row["id"] not in hyps,
            )
        )
    return sorted(results, key=lambda r: (r.kind, r.id))


def _rate(value: float | None, digits: int = 4) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def _counts_json(c: Counts) -> dict[str, int]:
    return {
        "hits": c.hits,
        "substitutions": c.substitutions,
        "deletions": c.deletions,
        "insertions": c.insertions,
    }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def summarize(results: list[SampleResult]) -> dict[str, dict]:
    """WER cấp corpus cho từng `kind`."""
    groups: dict[str, dict] = {}
    for kind in sorted({r.kind for r in results}):
        members = [r for r in results if r.kind == kind]
        c = corpus(r.score for r in members)
        groups[kind] = {
            "samples": c.samples,
            "missing": sum(r.missing for r in members),
            "ref_tokens": c.words.ref_len,
            **_counts_json(c.words),
            "wer": _round(c.words.rate),
            "mean_sample_wer": _round(c.mean_sample_wer),
            "ref_chars": c.chars.ref_len,
            "cer": _round(c.chars.rate),
            "wer_nodiac": _round(c.words_nodiac.rate),
        }
    return groups


def write_per_sample(path: Path, results: list[SampleResult]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PER_SAMPLE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in results:
            w = r.score.words
            writer.writerow(
                {
                    "id": r.id,
                    "source": r.source,
                    "kind": r.kind,
                    "split": r.split,
                    "ref_tokens": w.ref_len,
                    "hyp_tokens": w.hits + w.substitutions + w.insertions,
                    **_counts_json(w),
                    "wer": _rate(w.rate),
                    "ref_chars": r.score.chars.ref_len,
                    "char_errors": r.score.chars.errors,
                    "cer": _rate(r.score.chars.rate),
                    "wer_nodiac": _rate(r.score.words_nodiac.rate),
                    "missing": int(r.missing),
                }
            )


def _dump(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    """Đường dẫn tương đối từ gốc repo; ngoài repo thì chỉ ghi tên file (không lộ $HOME)."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _git() -> dict[str, object] | None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return {"sha": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return None


def normalizer_fingerprint() -> str:
    """sha256 của code và lexicon của normalizer: đổi quy tắc là đổi cách tính WER."""
    h = hashlib.sha256()
    for path in (Path(vi_normalize.__file__), vi_normalize.LEXICON_FILE):
        h.update(path.read_bytes())
    return h.hexdigest()


def environment(manifest: Path, hyp: Path, asr_meta: Path | None) -> dict[str, object]:
    return {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": _git(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "jiwer": metadata.version("jiwer"),
        "normalizer_sha256": normalizer_fingerprint(),
        "inputs": {
            "manifest": {"path": _display_path(manifest), "sha256": sha256_file(manifest)},
            "hyp": {"path": _display_path(hyp), "sha256": sha256_file(hyp)},
        },
        # Model, tham số và phần cứng của lần chạy ASR: do script chạy ASR ghi ra.
        "asr": json.loads(asr_meta.read_text(encoding="utf-8")) if asr_meta else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chấm WER cho output của một lần chạy ASR")
    parser.add_argument("--hyp", type=Path, required=True, help="file JSONL {id, text}")
    parser.add_argument("--tag", required=True, help="tên lần chạy, ví dụ whisper-small-int8")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--source", help="chỉ chấm nguồn này, ví dụ fleurs")
    parser.add_argument("--kind", help="chỉ chấm loại này, ví dụ read_speech")
    parser.add_argument("--split", help="chỉ chấm split này, ví dụ test")
    parser.add_argument("--allow-missing", action="store_true", help="thiếu hyp thì coi là rỗng")
    parser.add_argument("--asr-meta", type=Path, help="JSON mô tả model/tham số/phần cứng")
    parser.add_argument("--date", type=date.fromisoformat, default=None, help="mặc định hôm nay")
    parser.add_argument("--out", type=Path, help="thư mục kết quả, mặc định results/<date>_<tag>")
    parser.add_argument("--force", action="store_true", help="ghi đè thư mục kết quả đã có")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not TAG_PATTERN.match(args.tag):
        print("tag chỉ gồm chữ thường, số, '.', '_', '-'", file=sys.stderr)
        return 1
    out: Path = args.out or RESULTS / f"{(args.date or date.today()).isoformat()}_{args.tag}"

    try:
        if out.exists() and any(out.iterdir()) and not args.force:
            raise InputError(f"{_display_path(out)} đã có kết quả (dùng --force để ghi đè)")
        rows = load_manifest(args.manifest)
        selected = select_rows(rows, args.source, args.kind, args.split)
        if not selected:
            raise InputError("không có dòng nào trong manifest khớp điều kiện để chấm WER")
        results = evaluate(
            selected,
            {row["id"] for row in rows},
            load_hypotheses(args.hyp),
            args.manifest.parent,
            args.allow_missing,
        )
        env = environment(args.manifest, args.hyp, args.asr_meta)
    except (InputError, OSError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1

    groups = summarize(results)
    summary = {
        "tag": args.tag,
        "selection": {
            "source": args.source,
            "kind": args.kind,
            "split": args.split,
            "allow_missing": args.allow_missing,
        },
        "groups": groups,
    }
    out.mkdir(parents=True, exist_ok=True)
    write_per_sample(out / "per_sample.csv", results)
    (out / "summary.json").write_text(_dump(summary), encoding="utf-8")
    (out / "env.json").write_text(_dump(env), encoding="utf-8")
    make_report.write_report(out)

    for kind, g in groups.items():
        print(
            f"{kind}: {g['samples']} sample, WER {_rate(g['wer'])}, CER {_rate(g['cer'])}, "
            f"WER không dấu {_rate(g['wer_nodiac'])}, thiếu hyp {g['missing']}"
        )
    print(f"đã ghi {_display_path(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
