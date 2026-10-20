"""Spike ASR (AI-01): chạy một cấu hình faster-whisper trên các dòng của manifest.

    uv sync --group asr-spike
    uv run python spikes/asr/run_asr.py --model small --compute-type int8 --tag small-int8
    uv run python wer/run_wer.py --hyp spikes/asr/runs/small-int8/hyp.jsonl --tag small-int8 \\
      --asr-meta spikes/asr/runs/small-int8/meta.json --source fleurs

Ghi vào `spikes/asr/runs/<tag>/`:

- `hyp.jsonl`: mỗi dòng `{"id", "text", "audio_sec", "proc_sec"}`, đúng định dạng
  `wer/run_wer.py` nhận.
- `meta.json`: model, tham số, thiết bị, GPU, version, thời gian load model, tổng thời
  lượng audio, tổng thời gian xử lý, RTF, VRAM đỉnh.

Tham số giải mã theo kế hoạch: `language="vi"`, `condition_on_previous_text=False` và
lọc VAD để giảm hallucination. RTF = thời gian xử lý / thời lượng audio, gồm cả
decode bằng ffmpeg (vài chục ms mỗi file), không tính thời gian load model. VRAM đỉnh đo
bằng `nvidia-smi` mỗi 0.2 s, trừ mức đang dùng trước khi load model; GPU dùng chung với
tiến trình khác thì số này chỉ là xấp xỉ.

Nếu ASR lỗi trên một file, file đó vẫn có dòng trong `hyp.jsonl` với text rỗng và field
`error`, để `run_wer.py --allow-missing` không cần đoán.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import platform
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE.parents[1]
REPO_ROOT = EVAL_ROOT.parent
if str(EVAL_ROOT / "datasets") not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT / "datasets"))

import check_manifest  # noqa: E402

MANIFEST = EVAL_ROOT / "datasets" / "manifest.csv"
RUNS = HERE / "runs"
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# (text, thời lượng audio tính bằng giây) cho một file
Transcribe = Callable[[Path], tuple[str, float]]


@dataclass(frozen=True)
class DecodeParams:
    beam_size: int = 5
    vad_filter: bool = True
    condition_on_previous_text: bool = False
    language: str = "vi"
    # Ngưỡng mặc định của faster-whisper, ghi ra để meta.json đầy đủ.
    no_speech_threshold: float = 0.6
    compression_ratio_threshold: float = 2.4
    log_prob_threshold: float = -1.0


@dataclass
class RunResult:
    lines: list[dict] = field(default_factory=list)
    audio_sec: float = 0.0
    proc_sec: float = 0.0
    errors: int = 0


def select_rows(
    rows: list[dict[str, str]], source: str | None = None, kind: str | None = None
) -> list[dict[str, str]]:
    """Dòng có purpose `wer`, có reference, khớp bộ lọc; sắp theo id."""
    picked = [
        r
        for r in rows
        if "wer" in r["purpose"].split(";")
        and r["ref_path"]
        and (source is None or r["source"] == source)
        and (kind is None or r["kind"] == kind)
    ]
    return sorted(picked, key=lambda r: r["id"])


def transcribe_all(rows: Iterable[dict[str, str]], base: Path, transcribe: Transcribe) -> RunResult:
    result = RunResult()
    for row in rows:
        started = time.perf_counter()
        try:
            text, audio_sec = transcribe(base / row["audio_path"])
            line = {"id": row["id"], "text": text.strip(), "audio_sec": round(audio_sec, 3)}
        except Exception as e:  # noqa: BLE001 - ghi lại để tính vào WER, không dừng cả lượt
            audio_sec = float(row["duration_sec"])
            line = {"id": row["id"], "text": "", "audio_sec": audio_sec}
            line["error"] = type(e).__name__
            result.errors += 1
        proc = time.perf_counter() - started
        line["proc_sec"] = round(proc, 3)
        result.lines.append(line)
        result.audio_sec += audio_sec
        result.proc_sec += proc
    return result


class VramPeak:
    """Đo VRAM đỉnh (MiB) bằng nvidia-smi trong một thread. Không có GPU thì là None."""

    def __init__(self, interval: float = 0.2) -> None:
        self.interval = interval
        self.baseline = self._used()
        self.peak = self.baseline
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    @staticmethod
    def _used() -> int | None:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            return int(out.splitlines()[0])
        except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
            return None

    def _poll(self) -> None:
        while not self._stop.wait(self.interval):
            used = self._used()
            if used is not None and (self.peak is None or used > self.peak):
                self.peak = used

    def __enter__(self) -> VramPeak:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()

    @property
    def peak_above_baseline(self) -> int | None:
        if self.peak is None or self.baseline is None:
            return None
        return self.peak - self.baseline


def gpu_name() -> str | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return out.splitlines()[0].strip()
    except (OSError, subprocess.CalledProcessError, IndexError):
        return None


def preload_cuda_libs() -> None:
    """Nạp cuBLAS và cuDNN từ wheel `nvidia-*` để CTranslate2 tìm thấy.

    Wheel đặt thư viện trong site-packages/nvidia/*/lib, không nằm trong đường dẫn tìm
    kiếm của hệ thống. Nạp trước bằng đường dẫn tuyệt đối thì khỏi phải đặt
    LD_LIBRARY_PATH trước khi chạy Python.
    """
    try:
        import nvidia.cublas.lib
        import nvidia.cudnn.lib
    except ImportError:
        return
    for pkg in (nvidia.cublas.lib, nvidia.cudnn.lib):
        for lib in sorted(Path(next(iter(pkg.__path__))).glob("lib*.so*")):
            ctypes.CDLL(str(lib), mode=ctypes.RTLD_GLOBAL)


SAMPLE_RATE = 16000


def load_audio(path: Path, ffmpeg: str = "ffmpeg"):
    """Decode bằng ffmpeg sang float32 16 kHz mono, giống `audio.wav` của stage preprocess.

    Không dùng hàm decode của faster-whisper: bản 1.2.1 gọi `av.open(metadata_errors=...)`,
    tham số đã bị bỏ ở PyAV 15 trở lên, còn PyAV 14 không có wheel cho Python 3.13.
    """
    import numpy as np

    proc = subprocess.run(
        [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path)]
        + ["-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(proc.stdout, dtype=np.float32)


def faster_whisper_transcriber(
    model_name: str, device: str, compute_type: str, params: DecodeParams
) -> tuple[Transcribe, float]:
    """Load model, trả về hàm transcribe và thời gian load (giây)."""
    if device == "cuda":
        preload_cuda_libs()
    from faster_whisper import WhisperModel

    started = time.perf_counter()
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    load_sec = time.perf_counter() - started

    def transcribe(path: Path) -> tuple[str, float]:
        audio = load_audio(path)
        segments, info = model.transcribe(
            audio,
            language=params.language,
            beam_size=params.beam_size,
            vad_filter=params.vad_filter,
            condition_on_previous_text=params.condition_on_previous_text,
            no_speech_threshold=params.no_speech_threshold,
            compression_ratio_threshold=params.compression_ratio_threshold,
            log_prob_threshold=params.log_prob_threshold,
        )
        text = " ".join(s.text.strip() for s in segments)
        return text, info.duration

    return transcribe, load_sec


def _version(pkg: str) -> str | None:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def build_meta(
    args: argparse.Namespace,
    params: DecodeParams,
    result: RunResult,
    load_sec: float,
    vram_mib: int | None,
) -> dict[str, object]:
    return {
        "model": args.model,
        "compute_type": args.compute_type,
        "device": args.device,
        "gpu": gpu_name() if args.device == "cuda" else None,
        "params": params.__dict__,
        "faster_whisper": _version("faster-whisper"),
        "ctranslate2": _version("ctranslate2"),
        "python": platform.python_version(),
        "samples": len(result.lines),
        "errors": result.errors,
        "audio_sec": round(result.audio_sec, 3),
        "proc_sec": round(result.proc_sec, 3),
        "rtf": round(result.proc_sec / result.audio_sec, 4) if result.audio_sec else None,
        "model_load_sec": round(load_sec, 3),
        "vram_peak_mib": vram_mib,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chạy một cấu hình faster-whisper cho spike")
    parser.add_argument("--model", required=True, help="tên model faster-whisper hoặc đường dẫn")
    parser.add_argument("--tag", required=True, help="tên lần chạy, ví dụ small-int8")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--no-vad", action="store_true", help="tắt lọc VAD")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--source")
    parser.add_argument("--kind")
    parser.add_argument("--limit", type=int, help="chỉ chạy N file đầu, để thử nhanh")
    parser.add_argument("--out", type=Path, help="mặc định spikes/asr/runs/<tag>")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None, transcriber=faster_whisper_transcriber) -> int:
    args = build_parser().parse_args(argv)
    if not TAG_PATTERN.match(args.tag):
        print("tag chỉ gồm chữ thường, số, '.', '_', '-'", file=sys.stderr)
        return 1
    out: Path = args.out or RUNS / args.tag
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"{out} đã có kết quả (dùng --force để ghi đè)", file=sys.stderr)
        return 1

    _, rows = check_manifest.read_manifest(args.manifest)
    errors = check_manifest.check_rows(rows)
    if errors:
        print("manifest không hợp lệ:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    selected = select_rows(rows, args.source, args.kind)[: args.limit]
    if not selected:
        print("không có dòng nào để chạy", file=sys.stderr)
        return 1

    params = DecodeParams(beam_size=args.beam_size, vad_filter=not args.no_vad)
    with VramPeak() as vram:
        transcribe, load_sec = transcriber(args.model, args.device, args.compute_type, params)
        result = transcribe_all(selected, args.manifest.parent, transcribe)

    out.mkdir(parents=True, exist_ok=True)
    (out / "hyp.jsonl").write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in result.lines),
        encoding="utf-8",
    )
    meta = build_meta(args, params, result, load_sec, vram.peak_above_baseline)
    (out / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"{meta['samples']} file, lỗi {meta['errors']}, RTF {meta['rtf']}, "
        f"load {meta['model_load_sec']} s, VRAM đỉnh {meta['vram_peak_mib']} MiB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
