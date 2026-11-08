"""Fixture E2E: hết hạn audio tổng hợp rồi chạy CLI cleanup thật (FE-19)."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from app.db.models.meeting import Meeting
from app.db.models.transcript import Segment
from app.db.session import get_session_factory
from app.services.storage import get_storage
from sqlalchemy import select


def main() -> None:
    """Chỉ tác động meeting tổng hợp trong database E2E và appdata của stack test."""
    database = os.environ.get("E2E_DATABASE_URL", "")
    if "e2e" not in urlparse(database).path.lower() or database != os.environ.get(
        "DATABASE_URL"
    ):
        raise RuntimeError("Fixture chỉ chạy với DATABASE_URL=E2E_DATABASE_URL riêng.")
    meeting_id = str(UUID(sys.argv[1]))
    backend = Path(__file__).resolve().parents[2] / "backend"
    storage = get_storage()
    root = (backend / "appdata").resolve()
    if storage.base_dir.resolve() != root:
        raise RuntimeError("Storage không khớp thư mục QA dự kiến.")
    audio_dir = storage.get_audio_dir(meeting_id).resolve()
    artifacts_dir = (root / "artifacts" / meeting_id).resolve()
    if not audio_dir.is_relative_to(root) or not artifacts_dir.is_relative_to(root):
        raise RuntimeError("Đường dẫn cleanup nằm ngoài appdata.")

    session_factory = get_session_factory()
    with session_factory() as db:
        meeting = db.get(Meeting, meeting_id)
        if (
            not meeting
            or not meeting.title.startswith("E2E ")
            or meeting.status != "ready"
        ):
            raise RuntimeError("Chỉ hết hạn cuộc họp E2E ready vừa tạo.")
        if not meeting.audio_path or not (
            root / meeting.audio_path
        ).resolve().is_relative_to(audio_dir):
            raise RuntimeError("Audio không thuộc meeting tổng hợp cần kiểm tra.")
        if not audio_dir.exists() or not artifacts_dir.exists():
            raise RuntimeError("Phải có file thật trước cleanup để kiểm tra việc xóa.")
        before = [
            (s.id, s.text)
            for s in db.scalars(select(Segment).where(Segment.meeting_id == meeting_id))
        ]
        if not before:
            raise RuntimeError("Fixture phải có transcript trước khi hết hạn.")
        meeting.retention_until = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        expired = db.scalars(
            select(Meeting).where(
                Meeting.audio_path.is_not(None),
                Meeting.retention_until < datetime.now(UTC),
            )
        ).all()
        if any(not item.title.startswith("E2E ") for item in expired):
            raise RuntimeError(
                "Không chạy cleanup khi có dữ liệu hết hạn ngoài fixture E2E."
            )
        for item in expired:
            key = str(UUID(item.id))
            targets = [storage.get_audio_dir(key), root / "artifacts" / key]
            if any(not target.resolve().is_relative_to(root) for target in targets):
                raise RuntimeError("Đường dẫn ứng viên cleanup nằm ngoài appdata QA.")
        subprocess.run(
            [sys.executable, "-m", "app.scripts.cleanup"],
            cwd=backend,
            check=True,
            capture_output=True,
        )
        db.expire_all()
        after = [
            (s.id, s.text)
            for s in db.scalars(select(Segment).where(Segment.meeting_id == meeting_id))
        ]
        if (
            sorted(before) != sorted(after)
            or db.get(Meeting, meeting_id).audio_path is not None
        ):
            raise RuntimeError(
                "Cleanup không giữ nguyên transcript hoặc chưa xóa metadata audio."
            )
        if audio_dir.exists() or artifacts_dir.exists():
            raise RuntimeError("Cleanup chưa xóa file audio/artifacts thật.")
        print(
            json.dumps(
                {
                    "audio_removed": True,
                    "transcript_preserved": True,
                    "segments": len(after),
                }
            )
        )


if __name__ == "__main__":
    main()
