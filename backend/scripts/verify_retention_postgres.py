"""Script kiểm chứng chính sách lưu trữ (retention) 14 ngày (audio) và 28 ngày trên PostgreSQL.

Kịch bản kiểm chứng:
- Dữ liệu tổng hợp cuộc họp có tuổi 13, 14, 15 ngày:
  + 13 ngày (chưa hết hạn): audio, artifact và DB vẫn nguyên vẹn.
  + 14 ngày (đúng mốc biên retention_until): audio, artifact và DB vẫn nguyên vẹn (chưa xóa).
  + 15 ngày (quá hạn 14 ngày): audio và artifact trên đĩa bị xóa sạch; audio_path trong DB
    thành None (audio.available = false). Transcript và summary trong DB vẫn giữ nguyên vẹn.
- Dữ liệu vận hành (IdempotencyKey) có tuổi 27, 28, 29 ngày:
  + 27 ngày (chưa hết hạn): giữ nguyên trong DB.
  + 28 ngày (đúng mốc biên): giữ nguyên trong DB.
  + 29 ngày (quá hạn 28 ngày): bị xóa hoàn toàn khỏi DB.
"""

import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.idempotency import IdempotencyKey
from app.db.models.meeting import Meeting
from app.db.models.summary import Summary
from app.db.models.transcript import Segment, Speaker
from app.db.models.user import User
from app.services.retention import run_retention_cleanup
from app.services.storage.local import LocalStorage


def main() -> None:
    settings = get_settings()
    db_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    print(f"Connecting to Postgres at: {db_url}")
    engine = create_engine(db_url)

    # Thư mục storage tạm biệt lập cho bài test
    temp_dir = Path(tempfile.mkdtemp(prefix="retention_verify_"))
    storage = LocalStorage(base_dir=temp_dir)

    now = datetime(2026, 11, 12, 12, 0, 0, tzinfo=UTC)
    print(f"Test reference time (NOW): {now.isoformat()}")

    with Session(engine) as db:
        # 1. Tạo test user
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            email=f"retention_{user_id[:8]}@example.com",
            display_name="Retention Test User",
            password_hash="fake_hash",
        )
        db.add(user)
        db.commit()

        # 2. Tạo 3 cuộc họp với tuổi 13, 14, 15 ngày
        # Tuổi 13 ngày: retention_until = now + 1 ngày (chưa đến hạn)
        m13_id = str(uuid.uuid4())
        # Tuổi 14 ngày: retention_until = now (đúng lúc retention_until)
        m14_id = str(uuid.uuid4())
        # Tuổi 15 ngày: retention_until = now - 1 ngày (quá hạn 1 ngày)
        m15_id = str(uuid.uuid4())

        meetings_data = [
            (m13_id, 13, now + timedelta(days=1)),
            (m14_id, 14, now),
            (m15_id, 15, now - timedelta(days=1)),
        ]

        created_files: dict[str, dict[str, Path]] = {}

        for m_id, age_days, ret_until in meetings_data:
            audio_path = f"audio/{m_id}/original.wav"
            full_audio = storage.get_audio_path(m_id, "wav")
            full_audio.parent.mkdir(parents=True, exist_ok=True)
            full_audio.write_bytes(b"RIFF_FAKE_AUDIO_RETENTION_TEST")

            art_dir = temp_dir / "artifacts" / m_id / "job-1"
            art_dir.mkdir(parents=True, exist_ok=True)
            art_file = art_dir / "transcript.json"
            art_file.write_text('{"status": "ok", "segments": []}', encoding="utf-8")

            created_files[m_id] = {
                "audio": full_audio,
                "artifact": art_file,
                "art_dir": art_dir,
            }

            m = Meeting(
                id=m_id,
                owner_id=user_id,
                title=f"Cuộc họp tuổi {age_days} ngày",
                source="upload",
                status="ready",
                audio_path=audio_path,
                retention_until=ret_until,
                created_at=now - timedelta(days=age_days),
                updated_at=now - timedelta(days=age_days),
                version=1,
            )
            db.add(m)

            # Thêm speaker, segment, summary trong DB
            spk_id = str(uuid.uuid4())
            spk = Speaker(
                id=spk_id,
                meeting_id=m_id,
                label=f"SPEAKER_{age_days}",
                default_name=f"Speaker {age_days}",
                display_name=f"Người nói {age_days}d",
            )
            db.add(spk)
            seg = Segment(
                id=str(uuid.uuid4()),
                meeting_id=m_id,
                idx=0,
                start_sec=0.0,
                end_sec=5.0,
                speaker_id=spk_id,
                text=f"Nội dung cuộc họp tuổi {age_days} ngày.",
                ai_text=f"Nội dung cuộc họp tuổi {age_days} ngày.",
                version=1,
            )
            db.add(seg)
            summ = Summary(
                id=str(uuid.uuid4()),
                meeting_id=m_id,
                status="ready",
                content={"overview": f"Tóm tắt cuộc họp tuổi {age_days} ngày."},
            )
            db.add(summ)

        # 3. Tạo 3 IdempotencyKey với tuổi 27, 28, 29 ngày
        idem_27_id = str(uuid.uuid4())
        idem_28_id = str(uuid.uuid4())
        idem_29_id = str(uuid.uuid4())

        idem_data = [
            (idem_27_id, 27, now - timedelta(days=27)),
            (idem_28_id, 28, now - timedelta(days=28)),
            (idem_29_id, 29, now - timedelta(days=29)),
        ]

        for idem_id, age_days, c_at in idem_data:
            key_rec = IdempotencyKey(
                id=idem_id,
                user_id=user_id,
                key=f"idem_key_age_{age_days}d_{idem_id[:6]}",
                endpoint="/api/v1/meetings",
                status="completed",
                response_code=201,
                response_body={"status": "created"},
                created_at=c_at,
            )
            db.add(key_rec)

        db.commit()
        print("Đã khởi tạo thành công dữ liệu tổng hợp trên PostgreSQL:")
        print("  - Meeting 13d (retention_until = NOW + 1d)")
        print("  - Meeting 14d (retention_until = NOW)")
        print("  - Meeting 15d (retention_until = NOW - 1d)")
        print("  - IdempotencyKey 27d (created_at = NOW - 27d)")
        print("  - IdempotencyKey 28d (created_at = NOW - 28d)")
        print("  - IdempotencyKey 29d (created_at = NOW - 29d)")

        # 4. Thực thi run_retention_cleanup
        print("\n--- BẮT ĐẦU CHẠY RETENTION CLEANUP ---")
        result = run_retention_cleanup(db, storage=storage, now=now, dry_run=False)
        print(
            f"Cleanup Result: audio_expired_meetings={result.audio_expired_meetings}, "
            f"operational_keys_cleaned={result.operational_keys_cleaned}"
        )

        # 5. Kiểm chứng từng tài nguyên
        print("\n--- KẾT QUẢ KIỂM CHỨNG CHI TIẾT ---")

        # Meeting 13d
        m13 = db.execute(select(Meeting).where(Meeting.id == m13_id)).scalar_one()
        m13_audio_exists = created_files[m13_id]["audio"].exists()
        m13_art_exists = created_files[m13_id]["art_dir"].exists()
        m13_seg = db.execute(
            select(Segment).where(Segment.meeting_id == m13_id)
        ).scalar_one_or_none()
        print("Meeting 13 ngày (chưa hết hạn 14 ngày):")
        print(f"  - audio_path trong DB: {m13.audio_path} (KỲ VỌNG: còn nguyên)")
        print(f"  - File audio trên đĩa: {m13_audio_exists} (KỲ VỌNG: True)")
        print(f"  - Artifacts trên đĩa: {m13_art_exists} (KỲ VỌNG: True)")
        print(f"  - Transcript trong DB: {m13_seg is not None} (KỲ VỌNG: True)")
        assert m13.audio_path is not None
        assert m13_audio_exists
        assert m13_art_exists
        assert m13_seg is not None

        # Meeting 14d (tại đúng biên retention_until == now)
        m14 = db.execute(select(Meeting).where(Meeting.id == m14_id)).scalar_one()
        m14_audio_exists = created_files[m14_id]["audio"].exists()
        m14_art_exists = created_files[m14_id]["art_dir"].exists()
        m14_seg = db.execute(
            select(Segment).where(Segment.meeting_id == m14_id)
        ).scalar_one_or_none()
        print("Meeting 14 ngày (tại mốc biên retention_until == NOW):")
        print(
            f"  - audio_path trong DB: {m14.audio_path} (KỲ VỌNG: còn nguyên - đúng mốc chưa xóa)"
        )
        print(f"  - File audio trên đĩa: {m14_audio_exists} (KỲ VỌNG: True)")
        print(f"  - Artifacts trên đĩa: {m14_art_exists} (KỲ VỌNG: True)")
        print(f"  - Transcript trong DB: {m14_seg is not None} (KỲ VỌNG: True)")
        assert m14.audio_path is not None
        assert m14_audio_exists
        assert m14_art_exists
        assert m14_seg is not None

        # Meeting 15d (quá hạn 14 ngày)
        m15 = db.execute(select(Meeting).where(Meeting.id == m15_id)).scalar_one()
        m15_audio_exists = created_files[m15_id]["audio"].exists()
        m15_art_exists = created_files[m15_id]["art_dir"].exists()
        m15_seg = db.execute(
            select(Segment).where(Segment.meeting_id == m15_id)
        ).scalar_one_or_none()
        m15_summ = db.execute(
            select(Summary).where(Summary.meeting_id == m15_id)
        ).scalar_one_or_none()
        print("Meeting 15 ngày (quá hạn 14 ngày):")
        print(f"  - audio_path trong DB: {m15.audio_path} (KỲ VỌNG: None)")
        print(f"  - File audio trên đĩa: {m15_audio_exists} (KỲ VỌNG: False - ĐÃ XÓA)")
        print(f"  - Artifacts trên đĩa: {m15_art_exists} (KỲ VỌNG: False - ĐÃ XÓA)")
        print(f"  - Transcript trong DB: {m15_seg is not None} (KỲ VỌNG: True - VẪN GIỮ NGUYÊN)")
        print(f"  - Summary trong DB: {m15_summ is not None} (KỲ VỌNG: True - VẪN GIỮ NGUYÊN)")
        assert m15.audio_path is None
        assert not m15_audio_exists
        assert not m15_art_exists
        assert m15_seg is not None
        assert m15_summ is not None

        # Idempotency Keys
        k27 = db.execute(
            select(IdempotencyKey).where(IdempotencyKey.id == idem_27_id)
        ).scalar_one_or_none()
        k28 = db.execute(
            select(IdempotencyKey).where(IdempotencyKey.id == idem_28_id)
        ).scalar_one_or_none()
        k29 = db.execute(
            select(IdempotencyKey).where(IdempotencyKey.id == idem_29_id)
        ).scalar_one_or_none()
        print("Dữ liệu vận hành (IdempotencyKey):")
        print(
            f"  - Key 27 ngày (chưa hết hạn 28 ngày): Tồn tại = {k27 is not None} (KỲ VỌNG: True)"
        )
        print(
            f"  - Key 28 ngày (tại mốc biên 28 ngày): Tồn tại = {k28 is not None} (KỲ VỌNG: True)"
        )
        print(f"  - Key 29 ngày (quá hạn 28 ngày): Tồn tại = {k29 is not None} (KỲ VỌNG: False)")
        assert k27 is not None
        assert k28 is not None
        assert k29 is None

        # Dọn dẹp test data khỏi DB
        for m_id, _, _ in meetings_data:
            db.execute(Meeting.__table__.delete().where(Meeting.id == m_id))
            db.execute(Segment.__table__.delete().where(Segment.meeting_id == m_id))
            db.execute(Speaker.__table__.delete().where(Speaker.meeting_id == m_id))
            db.execute(Summary.__table__.delete().where(Summary.meeting_id == m_id))
        db.execute(IdempotencyKey.__table__.delete().where(IdempotencyKey.user_id == user_id))
        db.execute(User.__table__.delete().where(User.id == user_id))
        db.commit()

    # Xóa temp storage
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("\n✓ CÁC BIÊN RETENTION ĐÃ ĐƯỢC XÁC THỰC CHÍNH XÁC VỚI TÀI LIỆU VÀ POSTGRESQL!")


if __name__ == "__main__":
    main()
