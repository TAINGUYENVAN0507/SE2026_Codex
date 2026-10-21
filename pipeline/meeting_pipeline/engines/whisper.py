"""Engine thật dùng faster-whisper: ASR (Whisper qua CTranslate2) và VAD (Silero).

Cài bằng `uv sync --extra asr`. Thư viện chỉ được import trong hàm, nên package vẫn import
được trên CI không có faster-whisper.

Cấu hình qua biến môi trường, mặc định theo đề xuất trong `docs/adr/0001-asr.md`:

| Biến | Mặc định |
|---|---|
| `ASR_MODEL` | `large-v3-turbo` |
| `ASR_COMPUTE_TYPE` | `int8_float16` |
| `ASR_DEVICE` | `cuda` |
| `ASR_BEAM_SIZE` | `5` |

Audio được đọc từ `audio.wav` bằng module `wave` rồi đưa vào model dạng mảng float32.
Không dùng hàm decode của faster-whisper: bản 1.2.1 gọi `av.open(metadata_errors=...)`,
tham số này đã bị bỏ ở PyAV mới.
"""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from meeting_pipeline.engines.base import ProgressFn, WavAudio, load_float32
from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    TransientPipelineError,
)
from meeting_pipeline.stages.asr_post import RawSegment, RawWord

Loader = Callable[[WavAudio], Any]


@dataclass(frozen=True)
class WhisperConfig:
    model: str = "large-v3-turbo"
    compute_type: str = "int8_float16"
    device: str = "cuda"
    beam_size: int = 5
    language: str = "vi"

    @classmethod
    def from_env(cls) -> WhisperConfig:
        default = cls()
        return cls(
            model=os.environ.get("ASR_MODEL", default.model),
            compute_type=os.environ.get("ASR_COMPUTE_TYPE", default.compute_type),
            device=os.environ.get("ASR_DEVICE", default.device),
            beam_size=int(os.environ.get("ASR_BEAM_SIZE", default.beam_size)),
        )


def preload_cuda_libs() -> None:
    """Nạp cuBLAS và cuDNN từ wheel `nvidia-*` để CTranslate2 tìm thấy.

    Wheel đặt thư viện trong site-packages/nvidia/*/lib, ngoài đường dẫn tìm kiếm của hệ
    thống. Nạp trước bằng đường dẫn tuyệt đối thì không cần đặt LD_LIBRARY_PATH.
    """
    try:
        import nvidia.cublas.lib
        import nvidia.cudnn.lib
    except ImportError:
        return
    for pkg in (nvidia.cublas.lib, nvidia.cudnn.lib):
        for lib in sorted(Path(next(iter(pkg.__path__))).glob("lib*.so*")):
            ctypes.CDLL(str(lib), mode=ctypes.RTLD_GLOBAL)


def _is_oom(exc: BaseException) -> bool:
    return "out of memory" in str(exc).lower()


def _oom() -> TransientPipelineError:
    return TransientPipelineError(ErrorCode.OUT_OF_MEMORY, None, "hết bộ nhớ GPU khi chạy ASR")


class FasterWhisperAsr:
    """ASR bằng faster-whisper. `model_factory` và `loader` thay được trong test."""

    def __init__(
        self,
        config: WhisperConfig,
        model_factory: Callable[..., Any] | None = None,
        loader: Loader = load_float32,
    ) -> None:
        self.config = config
        self.name = f"faster-whisper:{config.model}:{config.compute_type}"
        self._model_factory = model_factory
        self._loader = loader

    def _load_model(self) -> Any:
        factory = self._model_factory
        try:
            if factory is None:
                if self.config.device == "cuda":
                    preload_cuda_libs()
                from faster_whisper import WhisperModel

                factory = WhisperModel
            return factory(
                self.config.model, device=self.config.device, compute_type=self.config.compute_type
            )
        except Exception as e:
            if _is_oom(e):
                raise _oom() from None
            # Không đưa message gốc vào lỗi: có thể chứa đường dẫn hoặc token.
            raise PermanentPipelineError(
                ErrorCode.MODEL_UNAVAILABLE,
                None,
                f"không load được model {self.config.model} ({type(e).__name__})",
            ) from None

    def transcribe(self, audio: WavAudio, progress: ProgressFn) -> list[RawSegment]:
        model = self._load_model()
        samples = self._loader(audio)
        try:
            segments, info = model.transcribe(
                samples,
                language=self.config.language,
                beam_size=self.config.beam_size,
                vad_filter=True,
                condition_on_previous_text=False,
                word_timestamps=True,
            )
            result = []
            for seg in segments:  # generator: giải mã thật sự chạy ở đây
                result.append(
                    RawSegment(
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                        avg_logprob=seg.avg_logprob,
                        no_speech_prob=seg.no_speech_prob,
                        compression_ratio=seg.compression_ratio,
                        words=tuple(
                            RawWord(w=w.word, s=w.start, e=w.end, p=w.probability)
                            for w in (seg.words or ())
                        ),
                    )
                )
                if info.duration:
                    progress(min(seg.end / info.duration, 1.0))
            return result
        except RuntimeError as e:
            if _is_oom(e):
                raise _oom() from None
            raise


@dataclass(frozen=True)
class SileroVad:
    """VAD bằng Silero (bản ONNX đóng gói trong faster-whisper), chạy trên CPU.

    Khác với VAD bên trong lúc transcribe (dùng để cắt audio thành đoạn dài), ở đây cần
    biên chính xác hơn: khoảng lặng từ 500 ms là tách region. Giá trị khởi tạo.
    """

    min_silence_duration_ms: int = 500
    speech_pad_ms: int = 200
    loader: Loader = load_float32
    name: str = "silero-vad (faster-whisper)"

    def speech_regions(self, audio: WavAudio) -> list[tuple[float, float]]:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        options = VadOptions(
            min_silence_duration_ms=self.min_silence_duration_ms,
            speech_pad_ms=self.speech_pad_ms,
        )
        stamps = get_speech_timestamps(self.loader(audio), options, sampling_rate=audio.sample_rate)
        return [(t["start"] / audio.sample_rate, t["end"] / audio.sample_rate) for t in stamps]
