"""Script seed dữ liệu mẫu cho môi trường phát triển và kiểm thử.

Tạo 1 tài khoản người dùng demo, 1 cuộc họp trạng thái ready kèm các speaker,
phân đoạn transcript, bản tóm tắt summary và 2 action items.
Script đảm bảo tính idempotent: chạy lại nhiều lần không sinh bản ghi trùng.
"""

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.action_item import ActionItem
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.db.session import get_session_factory

DEMO_USER_ID = "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d"
DEMO_USER_EMAIL = "demo@meeting.local"
DEMO_USER_NAME = "Demo User"
DEMO_MEETING_ID = "8f6c2a1e-b2c3-4d4e-8f9a-0b1c2d3e4f5a"


def _load_json_fixture(fixture_name: str) -> dict[str, Any]:
    """Đọc dữ liệu fixture từ thư mục contracts/fixtures/api/."""
    # Tìm thư mục gốc contracts/fixtures/api/
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    fixture_path = root_dir / "contracts" / "fixtures" / "api" / fixture_name
    if fixture_path.exists():
        with open(fixture_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def run_seed(session: Session) -> dict[str, int]:
    """Thực thi seed dữ liệu demo trên session được cung cấp.

    Trả về số lượng bản ghi được tạo mới cho từng loại thực thể.
    """
    stats = {
        "users_created": 0,
        "meetings_created": 0,
        "speakers_created": 0,
        "segments_created": 0,
        "summaries_created": 0,
        "action_items_created": 0,
    }

    # 1. Tạo User demo nếu chưa tồn tại
    user = session.execute(select(User).where(User.email == DEMO_USER_EMAIL)).scalar_one_or_none()
    if not user:
        raw_password = os.environ.get("SEED_DEMO_PASSWORD")
        if not raw_password:
            raise ValueError(
                "Thiếu biến môi trường SEED_DEMO_PASSWORD bắt buộc để seed tài khoản demo."
            )
        user = User(
            id=DEMO_USER_ID,
            email=DEMO_USER_EMAIL,
            display_name=DEMO_USER_NAME,
            password_hash=hash_password(raw_password),
        )
        session.add(user)
        session.flush()
        stats["users_created"] += 1

    # 2. Tạo Meeting demo nếu chưa tồn tại
    meeting = session.execute(
        select(Meeting).where(Meeting.id == DEMO_MEETING_ID)
    ).scalar_one_or_none()
    if not meeting:
        meeting = Meeting(
            id=DEMO_MEETING_ID,
            owner_id=user.id,
            title="Họp sprint 42 — upload audio và transcript",
            source="upload",
            status="ready",
            duration_sec=13.86,
            audio_path=f"audio/{DEMO_MEETING_ID}/original.mp3",
            audio_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            num_speakers_hint=2,
            meeting_date="2026-10-15",
            version=2,
        )
        session.add(meeting)
        session.flush()
        stats["meetings_created"] += 1

    # Đọc fixture transcript_ready.json
    transcript_data = _load_json_fixture("transcript_ready.json")
    speakers_data = transcript_data.get("speakers", [])
    segments_data = transcript_data.get("segments", [])

    # 3. Tạo Speakers nếu chưa tồn tại
    for sp_data in speakers_data:
        sp_id = sp_data["id"]
        existing_sp = session.execute(
            select(Speaker).where(Speaker.id == sp_id)
        ).scalar_one_or_none()
        if not existing_sp:
            speaker = Speaker(
                id=sp_id,
                meeting_id=meeting.id,
                label=sp_data["label"],
                default_name=sp_data["default_name"],
                display_name=sp_data["display_name"],
                version=sp_data.get("version", 1),
            )
            session.add(speaker)
            stats["speakers_created"] += 1
    session.flush()

    # 4. Tạo Segments nếu chưa tồn tại
    for seg_data in segments_data:
        seg_id = seg_data["id"]
        existing_seg = session.execute(
            select(Segment).where(Segment.id == seg_id)
        ).scalar_one_or_none()
        if not existing_seg:
            segment = Segment(
                id=seg_id,
                meeting_id=meeting.id,
                idx=seg_data.get("index", 0),
                start_sec=seg_data["start_sec"],
                end_sec=seg_data["end_sec"],
                speaker_id=seg_data.get("speaker_id"),
                ai_speaker_id=seg_data.get("ai_speaker_id"),
                text=seg_data["text"],
                ai_text=seg_data["ai_text"],
                confidence=seg_data.get("confidence"),
                flags=seg_data.get("flags", []),
                version=seg_data.get("version", 1),
            )
            session.add(segment)
            stats["segments_created"] += 1
    session.flush()

    # 5. Tạo Summary nếu chưa tồn tại
    summary_data = _load_json_fixture("summary_ready.json")
    existing_summary = session.execute(
        select(Summary).where(Summary.meeting_id == meeting.id)
    ).scalar_one_or_none()
    if not existing_summary and summary_data:
        summary = Summary(
            meeting_id=meeting.id,
            status=summary_data.get("status", "ready"),
            content=summary_data.get("content"),
            ai_content=summary_data.get("ai_content"),
            model=summary_data.get("model", "claude-opus-5-5"),
            prompt_version=summary_data.get("prompt_version", "summary-v1"),
            version=summary_data.get("version", 2),
        )
        session.add(summary)
        stats["summaries_created"] += 1
    session.flush()

    # 6. Tạo ActionItems nếu chưa tồn tại
    action_items_data = _load_json_fixture("action_items.json").get("items", [])
    for ai_data in action_items_data:
        ai_id = ai_data["id"]
        existing_ai = session.execute(
            select(ActionItem).where(ActionItem.id == ai_id)
        ).scalar_one_or_none()
        if not existing_ai:
            action_item = ActionItem(
                id=ai_id,
                meeting_id=meeting.id,
                description=ai_data["description"],
                assignee_name=ai_data.get("assignee_name"),
                assignee_speaker_id=ai_data.get("assignee_speaker_id"),
                due_date=ai_data.get("due_date"),
                due_date_text=ai_data.get("due_date_text"),
                status=ai_data.get("status", "open"),
                source=ai_data.get("source", "ai"),
                ai_original=ai_data.get("ai_original"),
                evidence_segment_ids=ai_data.get("evidence_segment_ids", []),
                needs_review=ai_data.get("needs_review", False),
                version=ai_data.get("version", 1),
            )
            session.add(action_item)
            stats["action_items_created"] += 1
    session.flush()

    session.commit()
    return stats


def main() -> None:
    """Điểm khởi chạy CLI cho lệnh python -m app.scripts.seed."""
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    session_factory = get_session_factory()
    with session_factory() as session:
        print("Bắt đầu thực hiện seed dữ liệu demo...")
        stats = run_seed(session)
        print("Kết quả seed:")
        for k, v in stats.items():
            print(f"  - {k}: {v}")
        print("Hoàn thành seed dữ liệu thành công.")


if __name__ == "__main__":
    main()
