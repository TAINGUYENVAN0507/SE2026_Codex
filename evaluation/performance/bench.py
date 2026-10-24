"""Benchmark pipeline thật: thời gian từng stage, RTF, RAM và VRAM đỉnh (AI-13).

Chạy bằng môi trường của `pipeline/` (cần `meeting_pipeline` và các extra model):

    cd pipeline
    uv run python ../evaluation/performance/bench.py --minutes 1 5 --tag gtx1650ti

- Audio: ghép các clip FLEURS trong `datasets/raw/fleurs_vi_test_audio/test/` theo thứ tự tên
  file cho tới khi đủ thời lượng, rồi cắt đúng thời lượng. Mỗi clip là một người đọc khác nhau,
  nên số speaker cao hơn cuộc họp thật; đây là benchmark tốc độ, không phải chất lượng.
- Chạy `run_job(backend="real")` như worker. Tóm tắt dùng `LLM_PROVIDER` của môi trường
  (mặc định `disabled`, không gọi API).
- Đo: thời gian từng stage (`PipelineOutcome.timings`, gồm cả thời gian nạp model), RTF =
  thời gian / thời lượng audio, RSS đỉnh của subprocess từng stage (cả process con, ví dụ
  ffmpeg) đọc từ `/proc`, VRAM đỉnh từ `nvidia-smi` nếu có. Lấy mẫu mỗi 0.5 s, nên đỉnh ngắn
  hơn khoảng đó có thể bị sót.
- Output: `performance/results/<YYYY-MM-DD>_<tag>/bench.csv` và `env.json`. Không chứa text.

File này chỉ import stdlib ở mức module, để pytest của `evaluation/` (không có
`meeting_pipeline`) vẫn test được các hàm thuần.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE.parent
REPO_ROOT = EVAL_ROOT.parent
FLEURS_DIR = EVAL_ROOT / "datasets" / "raw" / "fleurs_vi_test_audio" / "test"
RESULTS = HERE / "results"
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SAMPLE_SEC = 0.5
COLUMNS = [
    "target_min",
    "audio_sec",
    "stage",
    "status",
    "seconds",
    "rtf",
    "peak_rss_mb",
    "peak_vram_mb",
    "error_code",
]
# Biến môi trường ảnh hưởng tới tốc độ, ghi vào env.json.
TUNING_ENV = (
    "ASR_MODEL",
    "ASR_COMPUTE_TYPE",
    "ASR_DEVICE",
    "ASR_BEAM_SIZE",
    "DIARIZATION_MODEL",
    "DIARIZATION_DEVICE",
    "LLM_PROVIDER",
)


# ------------------------------------------------------------------ audio


def wav_duration(path: Path) -> float:
    """Thời lượng WAV đọc từ header RIFF: kích thước chunk `data` / `byte_rate` của `fmt `.

    Không dùng module `wave`: nó chỉ đọc PCM nguyên, còn FLEURS lưu float32 (format 3).
    """
    with path.open("rb") as f:
        head = f.read(12)
        if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError(f"{path.name} không phải WAV")
        byte_rate = 0
        while chunk := f.read(8):
            if len(chunk) < 8:
                break
            cid, size = chunk[:4], int.from_bytes(chunk[4:], "little")
            if cid == b"data":
                if not byte_rate:
                    break
                return size / byte_rate
            body = f.read(size + (size & 1))  # chunk lẻ có 1 byte đệm
            if cid == b"fmt ":
                byte_rate = int.from_bytes(body[8:12], "little")
    raise ValueError(f"{path.name} thiếu chunk fmt hoặc data")


def select_clips(clips: Iterable[tuple[Path, float]], target_sec: float) -> list[Path]:
    """Các clip đầu tiên (theo thứ tự đưa vào) có tổng thời lượng ≥ `target_sec`."""
    chosen, total = [], 0.0
    for path, seconds in clips:
        chosen.append(path)
        total += seconds
        # Dừng ngay khi đủ, không lấy thêm phần tử: `clips` có thể là generator đọc file.
        if total >= target_sec:
            return chosen
    raise ValueError(f"không đủ audio: có {total:.0f} s, cần {target_sec:.0f} s")


def fleurs_clips(folder: Path = FLEURS_DIR) -> Iterator[tuple[Path, float]]:
    """(clip, thời lượng) theo thứ tự tên file. Generator: chỉ đọc header của số clip cần dùng."""
    if not folder.is_dir():
        raise FileNotFoundError(f"chưa có {folder}: chạy datasets/download.py fleurs_vi_test_audio")
    for path in sorted(folder.glob("*.wav")):
        yield path, wav_duration(path)


def concat_command(clips: Sequence[Path], list_file: Path, out: Path, seconds: float) -> list[str]:
    """Lệnh ffmpeg ghép `clips` (đã ghi vào `list_file`) thành WAV 16 kHz mono dài `seconds`."""
    return [
        "ffmpeg",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-t",
        f"{seconds:.3f}",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(out),
    ]


def build_audio(target_sec: float, out: Path, clips: Iterable[tuple[Path, float]]) -> Path:
    chosen = select_clips(clips, target_sec)
    list_file = out.with_suffix(".txt")
    list_file.write_text("".join(f"file '{p}'\n" for p in chosen), encoding="utf-8")
    subprocess.run(concat_command(chosen, list_file, out, target_sec), check=True)
    return out


# ------------------------------------------------------------------ sampling


def stage_of(cmdline: Sequence[str]) -> str | None:
    """Tên stage nếu đây là subprocess `python -m meeting_pipeline run-stage <stage>`."""
    for i, arg in enumerate(cmdline[:-1]):
        if arg == "run-stage" and "meeting_pipeline" in cmdline[: i + 1]:
            return cmdline[i + 1]
    return None


def parse_nvidia_apps(text: str) -> dict[int, float]:
    """PID → MiB, từ `nvidia-smi --query-compute-apps=pid,used_memory --format=csv,...`."""
    usage: dict[int, float] = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[0].isdigit():
            try:
                usage[int(parts[0])] = usage.get(int(parts[0]), 0.0) + float(parts[1])
            except ValueError:
                continue
    return usage


def _proc_children() -> dict[int, list[int]]:
    children: dict[int, list[int]] = {}
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            # Field 2 (comm) có thể chứa khoảng trắng: tách sau dấu ")" cuối cùng.
            rest = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        children.setdefault(int(rest[1]), []).append(int(stat.parent.name))
    return children


def _rss_mb(pid: int) -> float:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def _cmdline(pid: int) -> list[str]:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")
    except OSError:
        return []


@dataclass
class Peaks:
    rss_mb: dict[str, float] = field(default_factory=dict)
    vram_mb: dict[str, float] = field(default_factory=dict)

    def update(self, stage: str, rss_mb: float, vram_mb: float | None) -> None:
        self.rss_mb[stage] = max(self.rss_mb.get(stage, 0.0), rss_mb)
        if vram_mb is not None:
            self.vram_mb[stage] = max(self.vram_mb.get(stage, 0.0), vram_mb)


class Sampler(threading.Thread):
    """Lấy mẫu RSS và VRAM của subprocess stage (cùng process con của nó) mỗi `SAMPLE_SEC`."""

    def __init__(self, root_pid: int) -> None:
        super().__init__(daemon=True)
        self.root_pid = root_pid
        self.peaks = Peaks()
        self.has_gpu = shutil.which("nvidia-smi") is not None
        self._done = threading.Event()

    def stop(self) -> Peaks:
        self._done.set()
        self.join(timeout=5)
        return self.peaks

    def _vram(self) -> dict[int, float] | None:
        if not self.has_gpu:
            return None
        try:
            out = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,used_memory",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            return None
        return parse_nvidia_apps(out)

    def run(self) -> None:
        while not self._done.wait(SAMPLE_SEC):
            tree = _proc_children()
            vram = self._vram()
            for pid in tree.get(self.root_pid, []):
                stage = stage_of(_cmdline(pid))
                if stage is None:
                    continue
                pids, todo = [], [pid]
                while todo:
                    p = todo.pop()
                    pids.append(p)
                    todo.extend(tree.get(p, []))
                rss = sum(_rss_mb(p) for p in pids)
                gpu = None if vram is None else sum(vram.get(p, 0.0) for p in pids)
                self.peaks.update(stage, rss, gpu)


# ------------------------------------------------------------------ run


def system_pressure() -> dict[str, object] | None:
    """PSI trung bình 60 s (CPU, IO, bộ nhớ) và load average. Ghi vào env.json, vì máy bận
    (ví dụ đang swap) làm chậm việc nạp model và làm số đo kém đại diện."""
    try:
        result: dict[str, object] = {}
        for kind in ("cpu", "io", "memory"):
            line = Path(f"/proc/pressure/{kind}").read_text().splitlines()[0]
            fields = dict(item.split("=") for item in line.split()[1:])
            result[f"{kind}_some_avg60"] = float(fields["avg60"])
        result["loadavg"] = [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
        return result
    except (OSError, IndexError, KeyError, ValueError):
        return None


def rtf(seconds: float, audio_sec: float) -> float:
    return round(seconds / audio_sec, 4)


def rows_for_run(
    target_min: float,
    audio_sec: float,
    stages: Sequence[str],
    status: dict[str, str],
    timings: dict[str, float],
    peaks: Peaks,
    error_code: str = "",
) -> list[dict[str, object]]:
    def mb(value: float | None) -> object:
        return "" if value is None else round(value)

    rows: list[dict[str, object]] = []
    for stage in stages:
        if stage not in status:
            continue
        seconds = timings.get(stage, 0.0)
        rows.append(
            {
                "target_min": target_min,
                "audio_sec": round(audio_sec, 3),
                "stage": stage,
                "status": status[stage],
                "seconds": round(seconds, 3),
                "rtf": rtf(seconds, audio_sec),
                "peak_rss_mb": mb(peaks.rss_mb.get(stage)),
                "peak_vram_mb": mb(peaks.vram_mb.get(stage)),
                "error_code": error_code if status[stage] == "failed" else "",
            }
        )
    total = sum(timings.values())
    rows.append(
        {
            "target_min": target_min,
            "audio_sec": round(audio_sec, 3),
            "stage": "total",
            "status": "failed" if error_code else "succeeded",
            "seconds": round(total, 3),
            "rtf": rtf(total, audio_sec),
            "peak_rss_mb": mb(max(peaks.rss_mb.values(), default=None)),
            "peak_vram_mb": mb(max(peaks.vram_mb.values(), default=None)),
            "error_code": error_code,
        }
    )
    return rows


def run_one(target_min: float, workdir: Path, audio: Path) -> list[dict[str, object]]:
    from meeting_pipeline.errors import PipelineError
    from meeting_pipeline.runner import run_job
    from meeting_pipeline.schemas import STAGES, JobSpec

    audio_sec = wav_duration(audio)
    spec = JobSpec(meeting_id="bench", job_id=f"bench-{target_min:g}m", audio_path=str(audio))
    started: dict[str, float] = {}
    timings: dict[str, float] = {}
    status: dict[str, str] = {}

    def on_progress(stage, value):
        started.setdefault(stage.value, time.monotonic())

    sampler = Sampler(os.getpid())
    sampler.start()
    t0 = time.monotonic()
    error_code = ""
    try:
        outcome = run_job(spec, workdir=workdir, on_progress=on_progress, backend="real")
        status = {s.value: v for s, v in outcome.stage_status.items()}
        timings = {s.value: v for s, v in outcome.timings.items()}
    except PipelineError as e:
        error_code = e.code.value
        failed = e.stage.value if e.stage else "unknown"
        # Stage đã xong có artifact; stage lỗi tính từ lúc báo progress đầu tiên.
        for s in STAGES:
            if s.value == failed:
                status[s.value] = "failed"
                timings[s.value] = time.monotonic() - started.get(s.value, t0)
                break
            status[s.value] = "succeeded"
    finally:
        peaks = sampler.stop()
    return rows_for_run(
        target_min, audio_sec, [s.value for s in STAGES], status, timings, peaks, error_code
    )


def _git() -> dict[str, object] | None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        dirty = git("status", "--porcelain", "--untracked-files=no")
        return {"sha": git("rev-parse", "HEAD"), "dirty": bool(dirty)}
    except (OSError, subprocess.CalledProcessError):
        return None


def _gpu() -> str | None:
    if shutil.which("nvidia-smi") is None:
        return None
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return out or None


def environment(minutes: Sequence[float]) -> dict[str, object]:
    from importlib import metadata

    def version(pkg: str) -> str | None:
        try:
            return metadata.version(pkg)
        except metadata.PackageNotFoundError:
            return None

    return {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": _git(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "gpu": _gpu(),
        "packages": {
            pkg: version(pkg)
            for pkg in ("faster-whisper", "ctranslate2", "pyannote.audio", "torch")
        },
        "env": {k: os.environ[k] for k in TUNING_ENV if k in os.environ},
        "audio": {"source": "fleurs_vi_test_audio/test", "minutes": list(minutes)},
        "sample_sec": SAMPLE_SEC,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--minutes", type=float, nargs="+", required=True)
    parser.add_argument("--tag", required=True, help="tên lần chạy, ví dụ gtx1650ti")
    parser.add_argument("--date", type=date.fromisoformat, default=None, help="mặc định hôm nay")
    parser.add_argument("--out", type=Path, help="mặc định performance/results/<date>_<tag>")
    parser.add_argument("--force", action="store_true", help="ghi đè thư mục kết quả đã có")
    args = parser.parse_args(argv)
    if not TAG_PATTERN.match(args.tag):
        parser.error("tag chỉ gồm chữ thường, số, '.', '_', '-'")

    out = args.out or RESULTS / f"{(args.date or date.today()).isoformat()}_{args.tag}"
    if out.exists() and not args.force:
        parser.error(f"{out} đã tồn tại (dùng --force để ghi đè)")
    env = environment(args.minutes)
    env["pressure"] = {}

    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="bench-") as tmp:
        for minutes in args.minutes:
            audio = build_audio(minutes * 60, Path(tmp) / f"{minutes:g}m.wav", fleurs_clips())
            print(f"bench {minutes:g}' ...", file=sys.stderr, flush=True)
            before = system_pressure()
            result = run_one(minutes, Path(tmp) / f"work-{minutes:g}m", audio)
            env["pressure"][f"{minutes:g}m"] = {"before": before, "after": system_pressure()}
            total = result[-1]
            print(
                f"  {total['status']} trong {total['seconds']} s (RTF {total['rtf']})",
                file=sys.stderr,
            )
            rows.extend(result)

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "bench.csv", rows)
    (out / "env.json").write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
