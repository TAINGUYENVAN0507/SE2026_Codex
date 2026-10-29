"""DTO đầu vào và contract đầu ra của module export, không phụ thuộc database."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Variant = Literal["current", "ai_original"]


class ExportModel(BaseModel):
    """Từ chối field lạ và số không hữu hạn trong dữ liệu xuất."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MeetingInfo(ExportModel):
    """Metadata công khai cần có trong biên bản."""

    id: str
    title: str
    meeting_date: date | None
    duration_sec: float | None = Field(ge=0)


class Speaker(ExportModel):
    """Tên người nói hiện tại và tên mặc định trước chỉnh sửa."""

    id: str
    display_name: str
    default_name: str


class Segment(ExportModel):
    """Phân đoạn có cả bản người dùng và bản AI bất biến."""

    id: str
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    text: str
    speaker_id: str | None
    ai_text: str
    ai_speaker_id: str | None

    @model_validator(mode="after")
    def check_time(self) -> "Segment":
        """Không xuất phân đoạn có khoảng thời gian đảo ngược."""
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec phải lớn hơn start_sec")
        return self


class SummaryPoint(ExportModel):
    """Ý chính hoặc quyết định và các đoạn bằng chứng."""

    text: str
    evidence_segment_ids: list[str] = Field(default_factory=list)


class SummaryContent(ExportModel):
    """Nội dung tóm tắt được xuất."""

    overview: str
    key_points: list[SummaryPoint] = Field(default_factory=list)
    decisions: list[SummaryPoint] = Field(default_factory=list)


class Summary(ExportModel):
    """Tóm tắt hiện tại và bản AI gốc, có thể chưa có nội dung."""

    content: SummaryContent | None
    ai_content: SummaryContent | None


class ActionOriginal(ExportModel):
    """Dữ liệu AI gốc của một công việc."""

    description: str
    assignee_name: str | None
    due_date: date | None
    due_date_text: str | None


class ActionItem(ActionOriginal):
    """Công việc hiện tại và dữ liệu cần chọn biến thể."""

    id: str
    status: Literal["open", "done", "cancelled"] = "open"
    source: Literal["ai", "user"] = "ai"
    ai_original: ActionOriginal | None


class MeetingExport(ExportModel):
    """Đầu vào do router của B tập hợp; không chứa ORM hoặc đường dẫn audio."""

    meeting: MeetingInfo
    speakers: list[Speaker]
    segments: list[Segment]
    summary: Summary | None
    action_items: list[ActionItem]


class ExportSpeaker(ExportModel):
    """Tên người nói trong biến thể đã chọn."""

    id: str
    name: str


class ExportSegment(ExportModel):
    """Phân đoạn chỉ chứa nội dung của biến thể đã chọn."""

    id: str
    start_sec: float
    end_sec: float
    speaker_id: str | None
    text: str


class ExportAction(ActionOriginal):
    """Công việc trong biến thể đã chọn."""

    id: str
    status: Literal["open", "done", "cancelled"]
    source: Literal["ai", "user"]


class ExportDocument(ExportModel):
    """JSON export v1; thứ tự field cũng là thứ tự key khi xuất."""

    schema_version: Literal["1.0"] = "1.0"
    variant: Variant
    meeting: MeetingInfo
    speakers: list[ExportSpeaker]
    segments: list[ExportSegment]
    summary: SummaryContent | None
    action_items: list[ExportAction]
