"""Engine diarization thật dùng pyannote.audio (AI-07).

Cài bằng `uv sync --extra diarize`. Thư viện chỉ được import trong hàm, nên package vẫn
import được trên CI không có pyannote hay torch.

| Biến | Mặc định |
|---|---|
| `DIARIZATION_MODEL` | `pyannote/speaker-diarization-community-1` (model gated) |
| `DIARIZATION_DEVICE` | `auto`: dùng CUDA nếu torch thấy GPU, ngược lại CPU |
| `HF_TOKEN` | Không đặt thì huggingface_hub dùng token đã lưu bằng `hf auth login` |

Audio được đọc từ `audio.wav` thành waveform rồi đưa thẳng vào pipeline, không để pyannote
tự decode file: tránh phụ thuộc vào bản FFmpeg mà torchcodec cần. Model gated: tài khoản
Hugging Face phải chấp nhận điều kiện sử dụng trên trang của model trước khi tải.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from meeting_pipeline.engines.base import WavAudio, load_float32
from meeting_pipeline.errors import (
    ErrorCode,
    PermanentPipelineError,
    TransientPipelineError,
)

RawTurn = tuple[float, float, str]


@dataclass(frozen=True)
class PyannoteConfig:
    model: str = "pyannote/speaker-diarization-community-1"
    device: str = "auto"

    @classmethod
    def from_env(cls) -> PyannoteConfig:
        default = cls()
        return cls(
            model=os.environ.get("DIARIZATION_MODEL", default.model),
            device=os.environ.get("DIARIZATION_DEVICE", default.device),
        )


def _is_oom(exc: BaseException) -> bool:
    return "out of memory" in str(exc).lower()


def _waveform(audio: WavAudio) -> Any:
    """Waveform dạng tensor (1, số mẫu) cho pyannote."""
    import torch

    return torch.from_numpy(load_float32(audio).copy()).unsqueeze(0)


def _load_pipeline(config: PyannoteConfig) -> Any:
    import torch
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(config.model, token=os.environ.get("HF_TOKEN") or None)
    if pipeline is None:  # pyannote trả None khi không tải được model gated
        raise RuntimeError("Pipeline.from_pretrained trả về None")
    device = config.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    return pipeline.to(torch.device(device))


class PyannoteDiarizer:
    """Diarization bằng pyannote. `pipeline_factory` và `loader` thay được trong test."""

    def __init__(
        self,
        config: PyannoteConfig,
        pipeline_factory: Callable[[PyannoteConfig], Any] = _load_pipeline,
        loader: Callable[[WavAudio], Any] = _waveform,
    ) -> None:
        self.config = config
        self.name = config.model
        self._pipeline_factory = pipeline_factory
        self._loader = loader

    def _pipeline(self) -> Any:
        try:
            return self._pipeline_factory(self.config)
        except Exception as e:
            if _is_oom(e):
                raise TransientPipelineError(
                    ErrorCode.OUT_OF_MEMORY, None, "hết bộ nhớ khi load model diarization"
                ) from None
            # Không đưa message gốc vào lỗi: có thể chứa token hoặc đường dẫn.
            raise PermanentPipelineError(
                ErrorCode.MODEL_UNAVAILABLE,
                None,
                f"không load được model {self.config.model} ({type(e).__name__})",
            ) from None

    def turns(self, audio: WavAudio, num_speakers: int | None = None) -> list[RawTurn]:
        pipeline = self._pipeline()
        waveform = self._loader(audio)
        try:
            output = pipeline(
                {"waveform": waveform, "sample_rate": audio.sample_rate},
                num_speakers=num_speakers,
            )
        except RuntimeError as e:
            if _is_oom(e):
                raise TransientPipelineError(
                    ErrorCode.OUT_OF_MEMORY, None, "hết bộ nhớ khi chạy diarization"
                ) from None
            raise
        # pyannote 4.x trả object có `.speaker_diarization`; bản 3.x trả thẳng Annotation.
        annotation = getattr(output, "speaker_diarization", output)
        return [
            (float(segment.start), float(segment.end), str(label))
            for segment, _, label in annotation.itertracks(yield_label=True)
        ]
