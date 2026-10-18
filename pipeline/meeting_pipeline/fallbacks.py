"""Output thay thế khi một stage không bắt buộc bị lỗi."""

from __future__ import annotations

from meeting_pipeline.schemas import DiarizeOutput, PipelineWarning, Stage

DIARIZATION_FALLBACK = "DIARIZATION_FALLBACK"


def diarization_fallback(reason: str = "") -> DiarizeOutput:
    """Diarization lỗi: không có turn nào, merge gộp toàn bộ thành 1 speaker.

    Người dùng vẫn đổi được speaker của từng segment bằng tay trên UI.
    """
    return DiarizeOutput(
        model=None,
        status="fallback",
        num_speakers=1,
        turns=[],
        warnings=[
            PipelineWarning(
                code=DIARIZATION_FALLBACK,
                stage=Stage.DIARIZE,
                message=reason or "không tách được speaker, gộp thành 1 speaker",
            )
        ],
    )
