"""Bộ đánh giá ồn synthetic: tạo audio theo `conditions.yaml`, chạy VAD và ASR, chấm WER (AI-12).

Bước 1, bằng môi trường của pipeline (cần extra `asr`, GPU nếu `ASR_DEVICE=cuda`):

    cd pipeline
    uv run python ../evaluation/noisy_audio/run_noisy.py transcribe --clips 10 --tag turbo-int8

Bước 2, bằng môi trường của evaluation:

    cd evaluation
    uv run python noisy_audio/run_noisy.py score noisy_audio/runs/turbo-int8

- Clip: `--clips` dòng đầu tiên (theo id) trong `datasets/manifest.csv` có source `fleurs`,
  purpose `wer` và có reference. Babble lấy từ các clip FLEURS khác trong thư mục raw.
- Mỗi file đi qua đúng đường của pipeline: VAD (dưới `MIN_SPEECH_SEC` lời nói thì coi như
  pipeline từ chối với `NO_SPEECH_DETECTED`, hypothesis rỗng), rồi ASR, rồi
  `normalize_segments` và `filter_hallucinations`. Model ASR chỉ nạp một lần.
- `transcribe` ghi `runs/<tag>/hyp.jsonl` (có text, vì FLEURS là dữ liệu công khai, cùng quy ước
  với `spikes/asr/runs/`) và `meta.json`. Với bản ghi họp nội bộ, đặt `--runs-dir` trong
  `datasets/private/`.
- `score` ghi `results/<ngày>_<tag>/`: `per_condition.csv`, `report.md`, `env.json`. Không
  chứa text. Cột `source=synthetic` để sau này tách với bản ghi thật (SH-01).
- WER của mỗi điều kiện là WER cấp corpus trên mọi clip, kèm chênh lệch so với `clean`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import make_noisy as mn

HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE.parent
REPO_ROOT = EVAL_ROOT.parent
DATASETS = EVAL_ROOT / "datasets"
MANIFEST = DATASETS / "manifest.csv"
FLEURS_DIR = DATASETS / "raw" / "fleurs_vi_test_audio" / "test"
RUNS = HERE / "runs"
RESULTS = HERE / "results"
# `score` dùng metrics và run_wer của evaluation/wer (không phải package).
if str(EVAL_ROOT / "wer") not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT / "wer"))
COLUMNS = [
    "source",
    "condition",
    "type",
    "snr_target_db",
    "snr_measured_db",
    "samples",
    "no_speech",
    "wer",
    "cer",
    "wer_nodiac",
    "delta_wer_vs_clean",
]


# ------------------------------------------------------------------ chọn dữ liệu


def read_manifest(path: Path = MANIFEST) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def select_clips(rows: Iterable[dict[str, str]], n: int) -> list[dict[str, str]]:
    eligible = [
        r
        for r in rows
        if r["source"] == "fleurs" and "wer" in r["purpose"].split(";") and r["ref_path"]
    ]
    chosen = sorted(eligible, key=lambda r: r["id"])[:n]
    if len(chosen) < n:
        raise ValueError(f"manifest chỉ có {len(chosen)} clip FLEURS có reference, cần {n}")
    return chosen


def babble_paths(folder: Path, exclude: set[str], count: int) -> list[Path]:
    """`count` clip FLEURS đầu tiên theo tên, không trùng clip đang đánh giá."""
    paths = [p for p in sorted(folder.glob("*.wav")) if p.stem not in exclude][:count]
    if len(paths) < count:
        raise ValueError(f"chỉ có {len(paths)} clip làm babble, cần {count}")
    return paths


# ------------------------------------------------------------------ transcribe

Transcriber = Callable[[Path], tuple[str, str]]  # (status, text)


def transcribe_suite(
    clips: Sequence[dict[str, str]],
    conditions: Sequence[mn.Condition],
    seed: int,
    babble: Sequence,
    transcriber: Transcriber,
    work: Path,
) -> list[dict[str, object]]:
    lines: list[dict[str, object]] = []
    for row in clips:
        clip = DATASETS / row["audio_path"]
        files = mn.make_noisy(clip, work / row["id"], conditions, seed, babble)
        clean = mn.read_audio(files["clean"])
        for cond in conditions:
            status, text = transcriber(files[cond.id])
            snr = None
            if cond.type in ("noise", "babble"):
                snr = round(float(mn.snr_db(clean, mn.read_audio(files[cond.id]))), 2)
            lines.append(
                {
                    "id": row["id"],
                    "condition": cond.id,
                    "status": status,
                    "snr_measured_db": snr,
                    "text": text,
                }
            )
    return lines


def pipeline_transcriber() -> tuple[Transcriber, dict[str, object]]:
    """VAD + ASR của pipeline, model nạp một lần. Chỉ chạy được trong môi trường pipeline."""
    from importlib import metadata

    from meeting_pipeline.engines import read_wav
    from meeting_pipeline.engines.whisper import (
        FasterWhisperAsr,
        SileroVad,
        WhisperConfig,
        preload_cuda_libs,
    )
    from meeting_pipeline.stages.asr_post import filter_hallucinations, normalize_segments
    from meeting_pipeline.stages.vad import MIN_SPEECH_SEC, to_spans

    config = WhisperConfig.from_env()
    if config.device == "cuda":
        preload_cuda_libs()
    from faster_whisper import WhisperModel

    started = time.monotonic()
    model = WhisperModel(config.model, device=config.device, compute_type=config.compute_type)
    load_sec = round(time.monotonic() - started, 3)
    asr = FasterWhisperAsr(config, model_factory=lambda *a, **k: model)
    vad = SileroVad()

    def transcribe(path: Path) -> tuple[str, str]:
        audio = read_wav(path)
        spans = to_spans(vad.speech_regions(audio), audio.duration_sec)
        if sum(s.end_sec - s.start_sec for s in spans) < MIN_SPEECH_SEC:
            return "no_speech", ""
        raw = asr.transcribe(audio, lambda _: None)
        segments, _ = filter_hallucinations(normalize_segments(raw, audio.duration_sec))
        return "ok", " ".join(s.text for s in segments)

    meta: dict[str, object] = {
        "asr": asr.name,
        "device": config.device,
        "beam_size": config.beam_size,
        "model_load_sec": load_sec,
        "min_speech_sec": MIN_SPEECH_SEC,
        "faster_whisper": metadata.version("faster-whisper"),
        "ctranslate2": metadata.version("ctranslate2"),
    }
    return transcribe, meta


def _gpu() -> str | None:
    import shutil
    import subprocess

    if shutil.which("nvidia-smi") is None:
        return None
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return out or None


def cmd_transcribe(args: argparse.Namespace) -> int:
    seed, conditions = mn.load_conditions(args.conditions)
    clips = select_clips(read_manifest(), args.clips)
    babble_files = babble_paths(FLEURS_DIR, {Path(r["audio_path"]).stem for r in clips}, 8)
    babble = [mn.read_audio(p) for p in babble_files]
    transcriber, asr_meta = pipeline_transcriber()

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="noisy-") as tmp:
        lines = transcribe_suite(clips, conditions, seed, babble, transcriber, Path(tmp))
    proc_sec = round(time.monotonic() - started, 3)

    run_dir = args.runs_dir or RUNS / args.tag
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "hyp.jsonl").open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    meta = {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tag": args.tag,
        "seed": seed,
        "conditions_sha256": hashlib.sha256(args.conditions.read_bytes()).hexdigest(),
        "conditions": [{"id": c.id, "type": c.type, **c.params} for c in conditions],
        "clips": [r["id"] for r in clips],
        "babble": [p.stem for p in babble_files],
        "gpu": _gpu(),
        "proc_sec": proc_sec,
        **asr_meta,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(run_dir)
    return 0


# ------------------------------------------------------------------ score


def per_condition(
    lines: Sequence[dict[str, object]],
    refs: dict[str, str],
    conditions: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    from metrics import corpus, score

    rows = []
    for cond in conditions:
        mine = [ln for ln in lines if ln["condition"] == cond["id"]]
        if not mine:
            raise ValueError(f"không có hypothesis nào cho điều kiện {cond['id']}")
        c = corpus(score(refs[str(ln["id"])], str(ln["text"])) for ln in mine)
        snrs = [float(ln["snr_measured_db"]) for ln in mine if ln["snr_measured_db"] is not None]
        rows.append(
            {
                "source": "synthetic",
                "condition": cond["id"],
                "type": cond["type"],
                "snr_target_db": cond.get("snr_db", ""),
                "snr_measured_db": round(sum(snrs) / len(snrs), 2) if snrs else "",
                "samples": len(mine),
                "no_speech": sum(ln["status"] == "no_speech" for ln in mine),
                "wer": round(c.words.rate, 4),
                "cer": round(c.chars.rate, 4),
                "wer_nodiac": round(c.words_nodiac.rate, 4),
            }
        )
    clean = next((r["wer"] for r in rows if r["condition"] == "clean"), None)
    for r in rows:
        r["delta_wer_vs_clean"] = "" if clean is None else round(float(r["wer"]) - clean, 4)
    return rows


def report(rows: Sequence[dict[str, object]], meta: dict[str, object]) -> str:
    lines = [
        f"# Bộ ồn synthetic: `{meta['tag']}`",
        "",
        f"- ASR: `{meta.get('asr')}` trên {meta.get('gpu') or meta.get('device')}",
        f"- {len(meta['clips'])} clip FLEURS × {len(rows)} điều kiện, seed {meta['seed']}",
        "- WER cấp corpus của mọi clip trong từng điều kiện. `no_speech`: số file VAD từ chối",
        "  (pipeline sẽ báo `NO_SPEECH_DETECTED`), chấm như hypothesis rỗng.",
        "",
        "| Điều kiện | SNR mục tiêu | SNR đo | WER | CER | Δ WER so với clean | no_speech |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        delta = r["delta_wer_vs_clean"]
        delta_text = "" if delta == "" else f"{float(delta):+.3f}"
        lines.append(
            f"| `{r['condition']}` | {r['snr_target_db']} | {r['snr_measured_db']} | "
            f"{float(r['wer']):.3f} | {float(r['cer']):.3f} | {delta_text} | {r['no_speech']} |"
        )
    return "\n".join(lines) + "\n"


def cmd_score(args: argparse.Namespace) -> int:
    import run_wer

    meta = json.loads((args.run_dir / "meta.json").read_text(encoding="utf-8"))
    lines = [
        json.loads(x)
        for x in (args.run_dir / "hyp.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    manifest = {r["id"]: r for r in read_manifest(args.manifest)}
    refs = {
        cid: (args.manifest.parent / manifest[cid]["ref_path"]).read_text(encoding="utf-8")
        for cid in meta["clips"]
    }
    rows = per_condition(lines, refs, meta["conditions"])

    out = args.out or RESULTS / f"{(args.date or date.today()).isoformat()}_{meta['tag']}"
    if out.exists() and not args.force:
        print(f"lỗi: {out} đã tồn tại (dùng --force để ghi đè)", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    with (out / "per_condition.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out / "report.md").write_text(report(rows, meta), encoding="utf-8")
    env = {
        "scored_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": run_wer._git(),
        "normalizer_sha256": run_wer.normalizer_fingerprint(),
        "hyp_sha256": hashlib.sha256((args.run_dir / "hyp.jsonl").read_bytes()).hexdigest(),
        "run": {k: v for k, v in meta.items() if k != "conditions"},
    }
    (out / "env.json").write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n")
    print(out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("transcribe", help="tạo bộ ồn và chạy VAD + ASR (môi trường pipeline)")
    t.add_argument("--clips", type=int, default=10)
    t.add_argument("--tag", required=True)
    t.add_argument("--conditions", type=Path, default=mn.CONDITIONS)
    t.add_argument("--runs-dir", type=Path, help="mặc định noisy_audio/runs/<tag>")
    s = sub.add_parser("score", help="chấm WER theo điều kiện (môi trường evaluation)")
    s.add_argument("run_dir", type=Path)
    s.add_argument("--manifest", type=Path, default=MANIFEST)
    s.add_argument("--date", type=date.fromisoformat, default=None)
    s.add_argument("--out", type=Path)
    s.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return cmd_transcribe(args) if args.command == "transcribe" else cmd_score(args)


if __name__ == "__main__":
    raise SystemExit(main())
