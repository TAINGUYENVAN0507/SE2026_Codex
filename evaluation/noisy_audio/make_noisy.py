"""Sinh audio ồn synthetic theo `conditions.yaml`, có seed (AI-12).

    uv run python noisy_audio/make_noisy.py --input clip.wav --out-dir /tmp/noisy \\
        --babble-dir datasets/raw/fleurs_vi_test_audio/test

- Đọc mọi định dạng bằng ffmpeg, đưa về 16 kHz mono float32. Ghi WAV PCM 16-bit.
- SNR tính trên chính tín hiệu: `10·log10(P_lời / P_ồn)`, P là trung bình bình phương trên
  toàn clip. Khi tín hiệu sau khi trộn vượt ngưỡng clip, cả lời và ồn được thu nhỏ cùng hệ
  số, nên SNR không đổi.
- Seed của mỗi file lấy từ `(seed, id điều kiện, tên clip)`: cùng input, cùng `conditions.yaml`
  thì ra cùng byte. Đổi thứ tự điều kiện không làm đổi output.
- Độ dài output bằng độ dài input (vọng bị cắt ở cuối), để timestamp của reference vẫn đúng.

Script này không gọi model. `run_noisy.py` dùng nó để tạo bộ ồn rồi chạy ASR.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import wave
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np
import yaml

SAMPLE_RATE = 16000
PEAK = 0.99
HERE = Path(__file__).resolve().parent
CONDITIONS = HERE / "conditions.yaml"

# Tham số bắt buộc của từng loại điều kiện, kèm khoảng giá trị hợp lệ.
SCHEMA: dict[str, dict[str, tuple[float, float] | tuple[str, ...]]] = {
    "clean": {},
    "noise": {"color": ("white", "pink", "brown"), "snr_db": (-10, 60)},
    "babble": {"talkers": (1, 10), "snr_db": (-10, 60)},
    "reverb": {"rt60_sec": (0.1, 3.0), "drr_db": (-10, 20)},
    "far_mic": {
        "lowpass_hz": (500, 7900),
        "rt60_sec": (0.1, 3.0),
        "drr_db": (-10, 20),
        "gain_db": (-40, 0),
    },
    "codec": {"codec": ("opus",), "bitrate_kbps": (6, 128)},
}


class ConditionError(ValueError):
    pass


@dataclass(frozen=True)
class Condition:
    id: str
    type: str
    params: dict[str, object] = field(default_factory=dict)


def _check_param(cond_id: str, name: str, value: object, allowed) -> object:
    if isinstance(allowed[0], str):
        if value not in allowed:
            raise ConditionError(f"{cond_id}: {name} phải là một trong {', '.join(allowed)}")
        return value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConditionError(f"{cond_id}: {name} phải là số")
    low, high = allowed
    if not low <= value <= high:
        raise ConditionError(f"{cond_id}: {name}={value} nằm ngoài khoảng [{low}, {high}]")
    return value


def parse_conditions(data: object) -> tuple[int, list[Condition]]:
    if not isinstance(data, dict) or not isinstance(data.get("conditions"), list):
        raise ConditionError("file điều kiện cần có `seed` và danh sách `conditions`")
    seed = data.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ConditionError("`seed` phải là số nguyên không âm")
    conditions, seen = [], set()
    for n, item in enumerate(data["conditions"], start=1):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ConditionError(f"điều kiện thứ {n}: cần `id` kiểu chuỗi")
        cond_id, kind = item["id"], item.get("type")
        if cond_id in seen:
            raise ConditionError(f"{cond_id}: id bị trùng")
        seen.add(cond_id)
        if kind not in SCHEMA:
            raise ConditionError(f"{cond_id}: type {kind!r} không hợp lệ ({', '.join(SCHEMA)})")
        expected = SCHEMA[kind]
        extra = set(item) - {"id", "type"} - set(expected)
        if extra:
            raise ConditionError(f"{cond_id}: tham số thừa {', '.join(sorted(extra))}")
        params = {}
        for name, allowed in expected.items():
            if name not in item:
                raise ConditionError(f"{cond_id}: thiếu {name}")
            params[name] = _check_param(cond_id, name, item[name], allowed)
        conditions.append(Condition(cond_id, kind, params))
    return seed, conditions


def load_conditions(path: Path = CONDITIONS) -> tuple[int, list[Condition]]:
    return parse_conditions(yaml.safe_load(path.read_text(encoding="utf-8")))


# ------------------------------------------------------------------ đọc, ghi


def read_audio(path: Path) -> np.ndarray:
    """Decode bằng ffmpeg thành float32 16 kHz mono."""
    out = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(path)]
        + ["-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(out, dtype="<f4").astype(np.float64)


def write_wav(path: Path, x: np.ndarray) -> Path:
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return path


# ------------------------------------------------------------------ tín hiệu


def rng_for(seed: int, condition_id: str, clip_key: str) -> np.random.Generator:
    return np.random.default_rng(
        [seed, zlib.crc32(condition_id.encode()), zlib.crc32(clip_key.encode())]
    )


def power(x: np.ndarray) -> float:
    return float(np.mean(np.square(x)))


def snr_db(clean: np.ndarray, noisy: np.ndarray) -> float:
    """SNR đo lại của `noisy` so với `clean` cùng độ dài, không phụ thuộc hệ số scale.

    Chiếu `noisy` lên `clean` (`g = <noisy, clean> / <clean, clean>`), phần còn lại là ồn. Vì
    vậy vẫn đúng khi `apply()` đã thu nhỏ cả tín hiệu để tránh clip.
    """
    g = float(np.dot(noisy, clean) / np.dot(clean, clean))
    residual = power(noisy - g * clean)
    return float("inf") if residual == 0 else 10 * np.log10(power(g * clean) / residual)


def colored_noise(n: int, color: str, rng: np.random.Generator) -> np.ndarray:
    """Ồn trắng, hồng (1/f) hoặc nâu (1/f²) theo công suất, chuẩn hóa về công suất 1."""
    white = rng.standard_normal(n)
    if color == "white":
        noise = white
    else:
        alpha = {"pink": 1.0, "brown": 2.0}[color]
        spectrum = np.fft.rfft(white)
        freqs = np.fft.rfftfreq(n, d=1 / SAMPLE_RATE)
        scale = np.zeros_like(freqs)
        scale[1:] = freqs[1:] ** (-alpha / 2)
        noise = np.fft.irfft(spectrum * scale, n)
    return noise / np.sqrt(power(noise))


def fit_length(x: np.ndarray, n: int) -> np.ndarray:
    """Lặp hoặc cắt `x` cho đủ `n` mẫu."""
    if len(x) >= n:
        return x[:n]
    return np.tile(x, -(-n // len(x)))[:n]


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr: float) -> np.ndarray:
    noise = fit_length(noise, len(speech))
    gain = np.sqrt(power(speech) / (power(noise) * 10 ** (snr / 10)))
    return speech + gain * noise


def reverb_ir(rt60: float, drr_db: float, rng: np.random.Generator) -> np.ndarray:
    """Impulse response tổng hợp: âm trực tiếp (mẫu 0) cộng đuôi ồn giảm 60 dB sau `rt60` giây.

    Năng lượng đuôi được chỉnh theo `drr_db` (tỉ lệ năng lượng trực tiếp / vọng). Phòng họp ở
    1–2 m thường có DRR từ 0 đến +5 dB; micro đặt xa thì âm.
    """
    n = int(rt60 * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    tail = rng.standard_normal(n) * np.exp(-6.908 * t / rt60)
    tail[0] = 0.0
    tail *= np.sqrt(10 ** (-drr_db / 10) / np.sum(np.square(tail)))
    tail[0] = 1.0
    return tail


def convolve_same(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    size = len(x) + len(ir) - 1
    nfft = 1 << (size - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)
    return y[: len(x)]


def match_power(y: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return y * np.sqrt(power(reference) / power(y))


def lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    """Lọc thông thấp trong miền tần số, dải chuyển tiếp cosine rộng 20 % của tần số cắt."""
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), d=1 / SAMPLE_RATE)
    start, stop = cutoff_hz * 0.9, cutoff_hz * 1.1
    mask = np.clip((stop - freqs) / (stop - start), 0.0, 1.0)
    mask = 0.5 - 0.5 * np.cos(np.pi * mask)
    return np.fft.irfft(spectrum * mask, len(x))


@cache
def _opus_args() -> tuple[str, ...]:
    encoders = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True
    ).stdout
    if " libopus " in encoders:
        return ("-c:a", "libopus")
    if " opus " in encoders:
        return ("-c:a", "opus", "-strict", "-2")
    raise ConditionError("ffmpeg không có encoder opus")


def codec_roundtrip(x: np.ndarray, bitrate_kbps: float) -> np.ndarray:
    with tempfile.TemporaryDirectory(prefix="noisy-codec-") as tmp:
        src, enc = Path(tmp) / "in.wav", Path(tmp) / "enc.ogg"
        write_wav(src, x)
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src)]
            + [*_opus_args(), "-b:a", f"{bitrate_kbps:g}k", str(enc)],
            check=True,
        )
        y = read_audio(enc)
    out = np.zeros(len(x))
    out[: min(len(x), len(y))] = y[: len(x)]
    return out


def apply(
    condition: Condition,
    speech: np.ndarray,
    rng: np.random.Generator,
    babble_sources: Sequence[np.ndarray] = (),
) -> np.ndarray:
    """Áp `condition` lên `speech` (float, 16 kHz mono). Output cùng độ dài, peak ≤ PEAK."""
    if power(speech) == 0:
        raise ConditionError("clip im lặng hoàn toàn, không tính được SNR")
    p = condition.params
    if condition.type == "clean":
        y = speech.copy()
    elif condition.type == "noise":
        y = mix_at_snr(speech, colored_noise(len(speech), str(p["color"]), rng), float(p["snr_db"]))
    elif condition.type == "babble":
        talkers = int(p["talkers"])
        if len(babble_sources) < talkers:
            raise ConditionError(
                f"{condition.id}: cần {talkers} giọng babble, có {len(babble_sources)}"
            )
        picks = rng.choice(len(babble_sources), size=talkers, replace=False)
        babble = sum(
            fit_length(babble_sources[i], len(speech)) / np.sqrt(power(babble_sources[i]))
            for i in sorted(picks)
        )
        y = mix_at_snr(speech, babble, float(p["snr_db"]))
    elif condition.type == "reverb":
        ir = reverb_ir(float(p["rt60_sec"]), float(p["drr_db"]), rng)
        y = match_power(convolve_same(speech, ir), speech)
    elif condition.type == "far_mic":
        y = lowpass(speech, float(p["lowpass_hz"]))
        ir = reverb_ir(float(p["rt60_sec"]), float(p["drr_db"]), rng)
        y = match_power(convolve_same(y, ir), speech)
        y = y * 10 ** (float(p["gain_db"]) / 20)
    elif condition.type == "codec":
        y = codec_roundtrip(speech, float(p["bitrate_kbps"]))
    else:  # parse_conditions đã chặn
        raise ConditionError(f"type không hợp lệ: {condition.type}")
    peak = float(np.max(np.abs(y)))
    return y * (PEAK / peak) if peak > PEAK else y


def make_noisy(
    clip: Path,
    out_dir: Path,
    conditions: Sequence[Condition],
    seed: int,
    babble_sources: Sequence[np.ndarray] = (),
) -> dict[str, Path]:
    """Ghi `<tên clip>__<id điều kiện>.wav` cho mọi điều kiện, trả về {id: đường dẫn}."""
    speech = read_audio(clip)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for cond in conditions:
        y = apply(cond, speech, rng_for(seed, cond.id, clip.stem), babble_sources)
        written[cond.id] = write_wav(out_dir / f"{clip.stem}__{cond.id}.wav", y)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--conditions", type=Path, default=CONDITIONS)
    parser.add_argument("--babble-dir", type=Path, help="thư mục WAV làm nguồn babble")
    parser.add_argument("--babble-count", type=int, default=8)
    args = parser.parse_args(argv)
    if shutil.which("ffmpeg") is None:
        parser.error("cần ffmpeg trong PATH")
    try:
        seed, conditions = load_conditions(args.conditions)
        babble = []
        if args.babble_dir:
            files = [p for p in sorted(args.babble_dir.glob("*.wav")) if p.stem != args.input.stem]
            babble = [read_audio(p) for p in files[: args.babble_count]]
        for cond_id, path in make_noisy(args.input, args.out_dir, conditions, seed, babble).items():
            print(f"{cond_id}\t{path}")
    except ConditionError as e:
        print(f"lỗi: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
