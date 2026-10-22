"""Chấm DER cho output diarization (AI-13).

    uv run python diarization/run_der.py --hyp-dir runs/pyannote/ --tag pyannote-community-1

- Reference: các dòng trong `datasets/manifest.csv` có purpose `der` và có `rttm_path`.
  Dữ liệu họp nội bộ nằm trong `datasets/private/` (không commit), nên chỉ chấm được trên
  máy có dữ liệu đó.
- Hypothesis: thư mục chứa `<id>.rttm`, mỗi file là RTTM của một sample. Cột URI trong file
  bị bỏ qua, id lấy theo tên file (stage diarize ghi URI là meeting_id).
- DER tính bằng pyannote.metrics, collar 0.25 s (mặc định), UEM là `[0, duration_sec]` của
  manifest. Báo cả hai bản: tính vùng nói chồng và bỏ qua vùng nói chồng (`skip_overlap`).
  Kèm sai số về số người nói.
- Output: `diarization/results/<YYYY-MM-DD>_<tag>/`: `per_sample.csv`, `summary.json` (theo
  từng `kind`, không gộp chung), `env.json`, `report.md`. Không chứa text.

Thiếu hypothesis là lỗi; `--allow-missing` chấm như hypothesis rỗng (toàn bộ là missed).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE.parent
for _sub in ("datasets", "normalizer", "wer"):
    if str(EVAL_ROOT / _sub) not in sys.path:
        sys.path.insert(0, str(EVAL_ROOT / _sub))

# Dùng chung cách đọc manifest và ghi provenance với bộ chấm WER.
import run_wer as common  # noqa: E402

MANIFEST = EVAL_ROOT / "datasets" / "manifest.csv"
RESULTS = HERE / "results"
COLLAR_SEC = 0.25

PER_SAMPLE_COLUMNS = [
    "id",
    "source",
    "kind",
    "duration_sec",
    "ref_speakers",
    "hyp_speakers",
    "total",
    "missed",
    "false_alarm",
    "confusion",
    "der",
    "der_skip_overlap",
    "missing",
]

Turn = tuple[float, float, str]


def read_rttm(path: Path) -> list[Turn]:
    """Các turn `(start, end, speaker)` của một file RTTM. Dòng trống và dòng `#` bị bỏ qua."""
    turns = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        try:
            if fields[0] != "SPEAKER" or len(fields) < 8:
                raise ValueError
            start, duration = float(fields[3]), float(fields[4])
        except ValueError:
            raise common.InputError(f"{path.name} dòng {n}: không phải dòng RTTM hợp lệ") from None
        if duration > 0:
            turns.append((start, start + duration, fields[7]))
    return turns


def _annotation(turns: list[Turn]):
    from pyannote.core import Annotation, Segment

    ann = Annotation()
    for i, (start, end, speaker) in enumerate(turns):
        ann[Segment(start, end), i] = speaker
    return ann


@dataclass(frozen=True)
class SampleResult:
    id: str
    source: str
    kind: str
    duration_sec: float
    ref_speakers: int
    hyp_speakers: int
    components: dict[str, float]
    der_skip_overlap: float
    missing: bool


def score(ref: list[Turn], hyp: list[Turn], duration: float, collar: float):
    """Thành phần DER (tính vùng nói chồng) và DER khi bỏ vùng nói chồng."""
    from pyannote.core import Segment, Timeline
    from pyannote.metrics.diarization import DiarizationErrorRate

    uem = Timeline([Segment(0, duration)])
    r, h = _annotation(ref), _annotation(hyp)
    full = DiarizationErrorRate(collar=collar, skip_overlap=False)(r, h, uem=uem, detailed=True)
    skip = DiarizationErrorRate(collar=collar, skip_overlap=True)(r, h, uem=uem)
    return full, skip


def evaluate(
    rows: list[dict[str, str]],
    base: Path,
    hyp_dir: Path,
    collar: float = COLLAR_SEC,
    allow_missing: bool = False,
) -> list[SampleResult]:
    missing = sorted(r["id"] for r in rows if not (hyp_dir / f"{r['id']}.rttm").exists())
    if missing and not allow_missing:
        raise common.InputError(
            f"{len(missing)} sample thiếu RTTM hypothesis: {', '.join(missing)} "
            "(dùng --allow-missing để chấm như hypothesis rỗng)"
        )
    results = []
    for row in rows:
        ref_path = base / row["rttm_path"]
        if not ref_path.exists():
            raise common.InputError(f"không có RTTM tham chiếu {row['rttm_path']}")
        ref = read_rttm(ref_path)
        hyp_path = hyp_dir / f"{row['id']}.rttm"
        hyp = read_rttm(hyp_path) if hyp_path.exists() else []
        duration = float(row["duration_sec"])
        full, skip = score(ref, hyp, duration, collar)
        results.append(
            SampleResult(
                id=row["id"],
                source=row["source"],
                kind=row["kind"],
                duration_sec=duration,
                ref_speakers=len({s for _, _, s in ref}),
                hyp_speakers=len({s for _, _, s in hyp}),
                components={
                    "total": full["total"],
                    "missed": full["missed detection"],
                    "false_alarm": full["false alarm"],
                    "confusion": full["confusion"],
                },
                der_skip_overlap=skip,
                missing=not hyp_path.exists(),
            )
        )
    return sorted(results, key=lambda r: (r.kind, r.id))


def _der(c: dict[str, float]) -> float | None:
    return (c["missed"] + c["false_alarm"] + c["confusion"]) / c["total"] if c["total"] else None


def summarize(results: list[SampleResult]) -> dict[str, dict]:
    """DER cấp corpus theo từng `kind`: cộng thời lượng lỗi rồi mới chia."""
    groups: dict[str, dict] = {}
    for kind in sorted({r.kind for r in results}):
        members = [r for r in results if r.kind == kind]
        totals = {k: sum(r.components[k] for r in members) for k in members[0].components}
        skip_err = [r.der_skip_overlap for r in members]
        groups[kind] = {
            "samples": len(members),
            "missing": sum(r.missing for r in members),
            **{k: round(v, 3) for k, v in totals.items()},
            "der": None if _der(totals) is None else round(_der(totals), 6),
            "mean_sample_der_skip_overlap": round(sum(skip_err) / len(skip_err), 6),
            "mean_abs_speaker_count_error": round(
                sum(abs(r.hyp_speakers - r.ref_speakers) for r in members) / len(members), 3
            ),
        }
    return groups


def write_per_sample(path: Path, results: list[SampleResult]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PER_SAMPLE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in results:
            c = r.components
            der = _der(c)
            writer.writerow(
                {
                    "id": r.id,
                    "source": r.source,
                    "kind": r.kind,
                    "duration_sec": f"{r.duration_sec:.3f}",
                    "ref_speakers": r.ref_speakers,
                    "hyp_speakers": r.hyp_speakers,
                    **{k: f"{c[k]:.3f}" for k in ("total", "missed", "false_alarm", "confusion")},
                    "der": "" if der is None else f"{der:.4f}",
                    "der_skip_overlap": f"{r.der_skip_overlap:.4f}",
                    "missing": int(r.missing),
                }
            )


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f} %"


def render_report(tag: str, collar: float, groups: dict[str, dict], env: dict) -> str:
    git = env.get("git") or {}
    lines = [
        f"# Kết quả DER: {tag}",
        "",
        "> Sinh tự động bởi `diarization/run_der.py`. Không sửa tay.",
        "",
        f"Collar {collar} s, UEM là `[0, duration_sec]` theo manifest.",
        "",
        "| Loại | Sample | Thiếu hyp | Tổng (s) | Missed (s) | False alarm (s) | Confusion (s) "
        "| DER | DER TB bỏ nói chồng | Sai số số speaker TB |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for kind, g in groups.items():
        lines.append(
            f"| `{kind}` | {g['samples']} | {g['missing']} | {g['total']} | {g['missed']} "
            f"| {g['false_alarm']} | {g['confusion']} | {_pct(g['der'])} "
            f"| {_pct(g['mean_sample_der_skip_overlap'])} | {g['mean_abs_speaker_count_error']} |"
        )
    lines += [
        "",
        "- DER = (missed + false alarm + confusion) / tổng thời lượng lời nói của reference, "
        "cộng dồn cả corpus.",
        f"- Git `{(git.get('sha') or '')[:12]}`"
        + (" (có thay đổi chưa commit)" if git.get("dirty") else ""),
        f"- pyannote.metrics {env.get('pyannote_metrics')}",
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chấm DER cho output diarization")
    parser.add_argument("--hyp-dir", type=Path, required=True, help="thư mục chứa <id>.rttm")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--collar", type=float, default=COLLAR_SEC)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not common.TAG_PATTERN.match(args.tag):
        print("tag chỉ gồm chữ thường, số, '.', '_', '-'", file=sys.stderr)
        return 1
    out: Path = args.out or RESULTS / f"{(args.date or date.today()).isoformat()}_{args.tag}"
    try:
        if out.exists() and any(out.iterdir()) and not args.force:
            raise common.InputError(f"{out.name} đã có kết quả (dùng --force để ghi đè)")
        rows = [
            r
            for r in common.load_manifest(args.manifest)
            if "der" in r["purpose"].split(";") and r["rttm_path"]
        ]
        if not rows:
            raise common.InputError("không có dòng nào trong manifest có purpose der và rttm_path")
        results = evaluate(
            rows, args.manifest.parent, args.hyp_dir, args.collar, args.allow_missing
        )
    except (common.InputError, OSError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1

    groups = summarize(results)
    env = {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": common._git(),
        "pyannote_metrics": metadata.version("pyannote.metrics"),
        "inputs": {
            "manifest": {
                "path": common._display_path(args.manifest),
                "sha256": common.sha256_file(args.manifest),
            },
            "hyp_dir": common._display_path(args.hyp_dir),
        },
    }
    summary = {"tag": args.tag, "collar_sec": args.collar, "groups": groups}
    out.mkdir(parents=True, exist_ok=True)
    write_per_sample(out / "per_sample.csv", results)
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "env.json").write_text(
        json.dumps(env, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "report.md").write_text(render_report(args.tag, args.collar, groups, env), "utf-8")
    for kind, g in groups.items():
        print(f"{kind}: {g['samples']} sample, DER {_pct(g['der'])}, thiếu hyp {g['missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
