"""Sinh `report.md` cho một thư mục kết quả WER (AI-11).

    uv run python wer/make_report.py wer/results/2026-10-19_whisper-small-int8

`run_wer.py` đã gọi sẵn bước này. Script chỉ cần khi muốn sinh lại report, ví dụ sau khi
sửa mẫu report. Report đọc `summary.json`, `per_sample.csv` và `env.json` trong cùng thư
mục, nên mọi con số trong report đều lấy từ lần chạy thật.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

WORST = 10
DEFAULT_MANIFEST = "evaluation/datasets/manifest.csv"
READ_SPEECH_NOTE = (
    "`read_speech` là giọng đọc (FLEURS, Common Voice, VIVOS), không đại diện cho hội thoại "
    "cuộc họp. Các loại dữ liệu được báo cáo riêng, không cộng gộp."
)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f} %"


def _cell(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace("|", "\\|").replace("\n", " ")


def _env_rows(env: dict | None) -> list[str]:
    if env is None:
        return ["| Môi trường | không có `env.json` |"]
    git = env.get("git")
    if git:
        dirty = " (có thay đổi chưa commit)" if git.get("dirty") else ""
        git_text = f"`{git['sha'][:12]}`{dirty}"
    else:
        git_text = "không xác định"
    inputs = env.get("inputs", {})
    rows = [
        f"| Thời điểm chạy | {env.get('created_at', '—')} |",
        f"| Git | {git_text} |",
        f"| Normalizer | `{env.get('normalizer_sha256', '')[:12]}` |",
        f"| jiwer | {env.get('jiwer', '—')} |",
    ]
    for name in ("manifest", "hyp"):
        if name in inputs:
            item = inputs[name]
            rows.append(f"| Input `{name}` | `{item['path']}` (sha256 `{item['sha256'][:12]}`) |")
    asr = env.get("asr")
    if isinstance(asr, dict) and asr:
        rows += [f"| ASR `{_cell(k)}` | {_cell(v)} |" for k, v in asr.items()]
    else:
        rows.append("| ASR | không có metadata (chạy `run_wer.py` không kèm `--asr-meta`) |")
    return rows


def _from_eval_dir(repo_path: str) -> str:
    """Đổi đường dẫn tính từ gốc repo (cách `env.json` ghi) sang tính từ `evaluation/`."""
    if repo_path.startswith("evaluation/"):
        return repo_path.removeprefix("evaluation/")
    # Không có "/" là file ngoài repo, chỉ biết tên.
    return f"../{repo_path}" if "/" in repo_path else repo_path


def _command(summary: dict, env: dict | None) -> str:
    inputs = (env or {}).get("inputs", {})
    hyp = _from_eval_dir(inputs.get("hyp", {}).get("path", "<hyp.jsonl>"))
    parts = ["uv run python wer/run_wer.py", f"--hyp {hyp}", f"--tag {summary['tag']}"]
    manifest = inputs.get("manifest", {}).get("path", DEFAULT_MANIFEST)
    if manifest != DEFAULT_MANIFEST:
        parts.append(f"--manifest {_from_eval_dir(manifest)}")
    selection = summary.get("selection", {})
    for opt in ("source", "kind", "split"):
        if selection.get(opt):
            parts.append(f"--{opt} {selection[opt]}")
    if selection.get("allow_missing"):
        parts.append("--allow-missing")
    return " ".join(parts)


def render(summary: dict, per_sample: list[dict[str, str]], env: dict | None) -> str:
    groups: dict[str, dict] = summary["groups"]
    lines = [
        f"# Kết quả WER: {summary['tag']}",
        "",
        "> Sinh tự động bởi `wer/make_report.py` từ `summary.json`, `per_sample.csv` và "
        "`env.json` trong cùng thư mục. Không sửa tay.",
        "",
        "## Kết quả theo loại dữ liệu",
        "",
        "| Loại | Sample | Thiếu hyp | Token ref | S | D | I | WER | WER TB mỗi sample | CER "
        "| WER không dấu |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for kind, g in groups.items():
        lines.append(
            f"| `{kind}` | {g['samples']} | {g['missing']} | {g['ref_tokens']} "
            f"| {g['substitutions']} | {g['deletions']} | {g['insertions']} | {_pct(g['wer'])} "
            f"| {_pct(g['mean_sample_wer'])} | {_pct(g['cer'])} | {_pct(g['wer_nodiac'])} |"
        )
    lines += [
        "",
        "- WER cấp corpus: tổng số lỗi chia cho tổng số token của reference. "
        "WER TB mỗi sample chỉ để tham khảo.",
        "- WER không dấu chỉ dùng để chẩn đoán lỗi thanh điệu, không thay cho WER.",
        "- Quy tắc chuẩn hóa: `normalizer/RULES.md`.",
    ]
    if "read_speech" in groups:
        lines.append(f"- {READ_SPEECH_NOTE}")

    missing = sum(g["missing"] for g in groups.values())
    git = (env or {}).get("git") or {}
    warnings = []
    if missing:
        warnings.append(
            f"{missing} sample thiếu hypothesis, được chấm như hypothesis rỗng (toàn lỗi xóa)."
        )
    if git.get("dirty"):
        warnings.append(
            "Lần chạy dùng code có thay đổi chưa commit: git SHA ở mục Môi trường không đủ "
            "để tái tạo kết quả."
        )
    if warnings:
        lines += ["", "## Lưu ý", "", *[f"- {w}" for w in warnings]]

    def errors(row: dict[str, str]) -> int:
        return int(row["substitutions"]) + int(row["deletions"]) + int(row["insertions"])

    worst = sorted(per_sample, key=lambda r: (-errors(r), r["id"]))[:WORST]
    worst = [r for r in worst if errors(r) > 0]
    lines += ["", f"## {WORST} sample nhiều lỗi nhất", ""]
    if worst:
        lines += ["| id | Loại | Token ref | Lỗi | WER |", "|---|---|---|---|---|"]
        for r in worst:
            wer = _pct(float(r["wer"])) if r["wer"] else "—"
            missing_mark = " (thiếu hyp)" if r["missing"] == "1" else ""
            lines.append(
                f"| `{r['id']}`{missing_mark} | `{r['kind']}` | {r['ref_tokens']} "
                f"| {errors(r)} | {wer} |"
            )
    else:
        lines.append("Không có sample nào có lỗi.")

    lines += [
        "",
        "## Môi trường",
        "",
        "| | |",
        "|---|---|",
        *_env_rows(env),
        "",
        "## Chạy lại",
        "",
        "```bash",
        "cd evaluation",
        _command(summary, env),
        "```",
        "",
        "Bảng Môi trường ghi đường dẫn tính từ gốc repo, lệnh trên tính từ `evaluation/`. "
        "File nằm ngoài repo chỉ được ghi tên. Kiểm tra sha256 trước khi so sánh hai lần chạy.",
    ]
    return "\n".join(lines) + "\n"


def write_report(results_dir: Path) -> Path:
    summary = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    with (results_dir / "per_sample.csv").open(encoding="utf-8", newline="") as f:
        per_sample = list(csv.DictReader(f))
    env_file = results_dir / "env.json"
    env = json.loads(env_file.read_text(encoding="utf-8")) if env_file.exists() else None
    path = results_dir / "report.md"
    path.write_text(render(summary, per_sample, env), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh report.md cho một thư mục kết quả WER")
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        path = write_report(args.results_dir)
    except (OSError, ValueError, KeyError) as e:
        print(f"không sinh được report: {e}", file=sys.stderr)
        return 1
    print(f"đã ghi {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
