"""Chọn implementation của từng stage theo backend.

`PIPELINE_BACKEND=fake` dùng fake stages (CI, dev backend/frontend).
`PIPELINE_BACKEND=real` (mặc định) dùng stage thật; stage nào chưa làm thì báo
`STAGE_NOT_IMPLEMENTED` thay vì âm thầm trả dữ liệu giả.
"""

from __future__ import annotations

import os
from typing import Literal

from meeting_pipeline.errors import ErrorCode, PermanentPipelineError
from meeting_pipeline.schemas import Stage
from meeting_pipeline.stages.base import StageContext, StageFn

Backend = Literal["real", "fake"]
BACKENDS: tuple[Backend, ...] = ("real", "fake")


def current_backend() -> Backend:
    value = os.environ.get("PIPELINE_BACKEND", "real")
    if value not in BACKENDS:
        raise PermanentPipelineError(
            ErrorCode.INTERNAL_ERROR, None, f"PIPELINE_BACKEND không hợp lệ: {value!r}"
        )
    return value  # type: ignore[return-value]


def _not_implemented(ctx: StageContext):
    raise PermanentPipelineError(
        ErrorCode.STAGE_NOT_IMPLEMENTED, ctx.stage, "stage thật chưa được cài đặt"
    )


def _real_stages() -> dict[Stage, StageFn]:
    # Import trong hàm để các stage nặng (model) chỉ được nạp khi thật sự dùng.
    from meeting_pipeline.stages import preprocess

    return {Stage.PREPROCESS: preprocess.run}


def get_stage(stage: Stage, backend: Backend | None = None) -> StageFn:
    backend = backend or current_backend()
    if backend == "fake":
        from meeting_pipeline.fake.stages import FAKE_STAGES

        return FAKE_STAGES[stage]
    return _real_stages().get(stage, _not_implemented)
