"""Stage preprocess (AI-05): kiểm tra file gốc và chuẩn hóa audio cho các stage AI.

1. `ffprobe` đọc container, codec, sample rate, số kênh. Không có audio stream là lỗi.
2. `ffmpeg` decode sang WAV 16 kHz mono PCM s16 (`audio.wav`) cho VAD/ASR/diarization.
3. Duration lấy từ số frame của file WAV đã decode, không tin header: WebM do
   MediaRecorder ghi thường thiếu duration.
4. Chọn file để phát lại trên trình duyệt: giữ file gốc nếu trình duyệt phát được,
   ngược lại transcode sang AAC (`playback.m4a`).

Giới hạn thời lượng đọc từ môi trường lúc chạy:
`PIPELINE_MIN_DURATION_SEC` (mặc định 1) và `PIPELINE_MAX_DURATION_SEC` (mặc định 3600).
"""

from __future__ import annotations

import json
import os
import subprocess
import wave
from pathlib import Path

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import (
    AUDIO_FILE,
    PipelineWarning,
    PlaybackInfo,
    PreprocessOutput,
    SourceAudioInfo,
)
from meeting_pipeline.stages.base import StageContext

TARGET_SAMPLE_RATE = 16000
PLAYBACK_FILE = "playback.m4a"

# Container (theo format_name của ffprobe) -> (mime type, các codec trình duyệt phát được).
_PLAYABLE: dict[str, tuple[str, frozenset[str]]] = {
    "mp3": ("audio/mpeg", frozenset({"mp3"})),
    "mov,mp4,m4a,3gp,3g2,mj2": ("audio/mp4", frozenset({"aac", "mp3"})),
    "matroska,webm": ("audio/webm", frozenset({"opus", "vorbis"})),
    "ogg": ("audio/ogg", frozenset({"opus", "vorbis", "flac"})),
    "wav": ("audio/wav", frozenset({"pcm_s16le", "pcm_u8"})),
    "flac": ("audio/flac", frozenset({"flac"})),
}


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


def _ffmpeg() -> str:
    return os.environ.get("FFMPEG_BIN", "ffmpeg")


def _ffprobe() -> str:
    return os.environ.get("FFPROBE_BIN", "ffprobe")


def probe(path: Path) -> dict:
    proc = subprocess.run(
        [_ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams"]
        + [str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise PermanentPipelineError(
            ErrorCode.AUDIO_INVALID, None, "ffprobe không đọc được file (hỏng hoặc sai định dạng)"
        )
    try:
        return json.loads(proc.stdout)
    except ValueError:
        raise PermanentPipelineError(
            ErrorCode.AUDIO_INVALID, None, "ffprobe trả về dữ liệu không hợp lệ"
        ) from None


def _to_int(value: object) -> int | None:
    try:
        return int(str(value))
    except ValueError:
        return None


def _to_float(value: object) -> float | None:
    try:
        return float(str(value))
    except ValueError:
        return None


def _run_ffmpeg(args: list[str], what: str) -> None:
    proc = subprocess.run(
        [_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise PermanentPipelineError(ErrorCode.AUDIO_INVALID, None, f"ffmpeg không {what} được")


def decode_to_wav(src: Path, dst: Path) -> float:
    """Decode audio stream đầu tiên sang WAV 16 kHz mono s16. Trả về duration (giây)."""
    tmp = dst.with_name(f".{dst.name}.tmp")
    try:
        _run_ffmpeg(
            ["-i", str(src), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(TARGET_SAMPLE_RATE)]
            + ["-c:a", "pcm_s16le", "-f", "wav", str(tmp)],
            "decode",
        )
        with wave.open(str(tmp), "rb") as w:
            duration = w.getnframes() / w.getframerate()
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)
    return round(duration, 3)


def _playback(src: Path, workdir: Path, format_name: str, codec: str | None) -> PlaybackInfo:
    mime, codecs = _PLAYABLE.get(format_name, (None, frozenset()))
    if mime is not None and codec in codecs:
        return PlaybackInfo(source="original", file=None, mime_type=mime)

    tmp = workdir / f".tmp.{PLAYBACK_FILE}"
    try:
        _run_ffmpeg(
            ["-i", str(src), "-map", "0:a:0", "-vn", "-c:a", "aac", "-b:a", "96k", str(tmp)],
            "tạo file phát lại",
        )
        os.replace(tmp, workdir / PLAYBACK_FILE)
    finally:
        tmp.unlink(missing_ok=True)
    return PlaybackInfo(source="transcoded", file=PLAYBACK_FILE, mime_type="audio/mp4")


def run(ctx: StageContext) -> PreprocessOutput:
    try:
        return _run(ctx)
    except PermanentPipelineError as e:
        e.stage = ctx.stage
        (ctx.workdir / AUDIO_FILE).unlink(missing_ok=True)
        raise


def _run(ctx: StageContext) -> PreprocessOutput:
    src = Path(ctx.spec.audio_path)
    if not src.is_file():
        raise PermanentPipelineError(ErrorCode.MISSING_INPUT, ctx.stage, "không tìm thấy file gốc")

    info = probe(src)
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        raise PermanentPipelineError(ErrorCode.AUDIO_INVALID, ctx.stage, "file không có audio")
    stream = streams[0]
    fmt = info.get("format", {})
    format_name = str(fmt.get("format_name", ""))
    codec = stream.get("codec_name")
    header_duration = _to_float(fmt.get("duration"))
    ctx.progress(0.1)

    duration = decode_to_wav(src, ctx.workdir / AUDIO_FILE)
    ctx.progress(0.7)

    min_sec = _env_float("PIPELINE_MIN_DURATION_SEC", 1.0)
    max_sec = _env_float("PIPELINE_MAX_DURATION_SEC", 3600.0)
    if duration < min_sec:
        raise PermanentPipelineError(
            ErrorCode.AUDIO_TOO_SHORT,
            ctx.stage,
            f"audio dài {duration:.2f} s, tối thiểu {min_sec:.0f} s",
            {"duration_sec": duration, "min_duration_sec": min_sec},
        )
    if duration > max_sec:
        raise PermanentPipelineError(
            ErrorCode.AUDIO_TOO_LONG,
            ctx.stage,
            f"audio dài {duration:.0f} s, tối đa {max_sec:.0f} s",
            {"duration_sec": duration, "max_duration_sec": max_sec},
        )

    warnings: list[PipelineWarning] = []
    if len(streams) > 1:
        warnings.append(
            PipelineWarning(
                code="MULTIPLE_AUDIO_STREAMS",
                stage=ctx.stage,
                message=f"file có {len(streams)} audio stream, chỉ dùng stream đầu tiên",
            )
        )
    if header_duration is not None and abs(header_duration - duration) > max(1.0, 0.05 * duration):
        warnings.append(
            PipelineWarning(
                code="HEADER_DURATION_MISMATCH",
                stage=ctx.stage,
                message=f"header ghi {header_duration:.1f} s, decode được {duration:.1f} s",
            )
        )

    playback = _playback(src, ctx.workdir, format_name, codec)
    ctx.progress(0.95)

    return PreprocessOutput(
        duration_sec=duration,
        source=SourceAudioInfo(
            format_name=format_name or None,
            codec=codec,
            sample_rate=_to_int(stream.get("sample_rate")),
            channels=_to_int(stream.get("channels")),
            header_duration_sec=header_duration,
            size_bytes=src.stat().st_size,
        ),
        playback=playback,
        warnings=warnings,
    )
