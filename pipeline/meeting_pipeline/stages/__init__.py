"""Các stage của pipeline và khung chạy chung."""

from meeting_pipeline.stages.base import StageContext, StageFn, execute_stage

__all__ = ["StageContext", "StageFn", "execute_stage"]
