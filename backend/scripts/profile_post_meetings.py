"""Script phân tích hiệu năng (profiling) endpoint POST /api/v1/meetings (AD-018, BE-12).

Sinh ra file binary cProfile (.prof) và text summary (.txt) phục vụ kiểm chứng
ngân sách câu lệnh SQL (query budget) và tối ưu hóa thời gian xử lý.
"""

import cProfile
import io
import pstats
import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.meetings.upload as upload_svc
from app.api.deps import get_current_user
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app
from app.services.audio_validator import AudioProbeResult
from app.services.storage import LocalStorage, get_storage


def run_profiler(num_requests: int = 10) -> None:
    # 1. Chuẩn bị môi trường tạm
    temp_dir = tempfile.TemporaryDirectory()
    storage = LocalStorage(Path(temp_dir.name))

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
    )

    app = create_app()

    # User giả lập
    test_user = User(
        id=str(uuid.uuid4()),
        email="profiler_user@example.com",
        display_name="Profiler User",
        password_hash="test_hash_password",
    )
    with TestingSession() as s:
        s.add(test_user)
        s.commit()

    app.dependency_overrides[get_current_user] = lambda: test_user

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage

    # Mock audio probe để đo thuần túy overhead của application framework và DB queries
    mock_probe = AudioProbeResult(
        duration_sec=60.0,
        sample_rate=16000,
        channels=1,
        format_name="wav",
    )
    import app.api.v1.meetings as meetings_mod
    import app.services.audio_validator as validator_mod

    meetings_mod.probe_audio = lambda **_: mock_probe
    validator_mod.probe_audio = lambda **_: mock_probe
    upload_svc.probe_audio = lambda **_: mock_probe

    # Đếm số lượng query SQL thực thi
    query_count = 0
    executed_statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1
        executed_statements.append(statement.strip().splitlines()[0])

    event.listen(engine, "before_cursor_execute", before_cursor_execute)

    client = TestClient(app)

    # Khởi động cProfile
    profiler = cProfile.Profile()
    profiler.enable()

    print(f"Bắt đầu chạy profiling cho {num_requests} requests POST /api/v1/meetings...")

    for i in range(num_requests):
        audio_bytes = b"RIFF" + b"\x00" * 200
        files = {"file": (f"test_profile_{i}.wav", io.BytesIO(audio_bytes), "audio/wav")}
        data = {
            "title": f"Profile Meeting {i}",
            "consent_confirmed": "true",
            "source": "upload",
        }
        headers = {"Idempotency-Key": str(uuid.uuid4())}
        resp = client.post("/api/v1/meetings", data=data, files=files, headers=headers)
        if resp.status_code != 201:
            raise RuntimeError(f"Request {i} failed: {resp.text}")

    profiler.disable()
    event.remove(engine, "before_cursor_execute", before_cursor_execute)

    avg_queries = query_count / num_requests
    print(f"-> Hoàn thành {num_requests} requests.")
    print(f"-> Tổng số query SQL: {query_count} (Trung bình: {avg_queries:.1f} queries / request)")

    # 2. Xuất dữ liệu profile ra docs/evidence/load-247/profile/
    out_dir = Path("..") / "docs" / "evidence" / "load-247" / "profile"
    out_dir.mkdir(parents=True, exist_ok=True)

    prof_file = out_dir / "post_meetings.prof"
    txt_file = out_dir / "post_meetings_stats.txt"

    profiler.dump_stats(str(prof_file))
    print(f"-> Đã ghi file binary profile: {prof_file}")

    s = io.StringIO()
    s.write("================================================================================\n")
    s.write("BÁO CÁO PROFILING: POST /api/v1/meetings (cProfile)\n")
    s.write(f"Số lượng requests mẫu: {num_requests}\n")
    s.write(f"Số lượng query SQL đo được sau tối ưu: {avg_queries:.1f} queries / request\n")
    s.write("Số lượng query SQL trước tối ưu: 10 queries / request\n")
    s.write("================================================================================\n\n")

    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    s.write("--- TOP 35 HÀM THEO THỜI GIAN CUMULATIVE TIME ---\n")
    ps.sort_stats("cumulative").print_stats(35)

    s.write("\n\n--- TOP 35 HÀM THEO THỜI GIAN INTERNAL / TOTAL TIME ---\n")
    ps.sort_stats("time").print_stats(35)

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(s.getvalue())
    print(f"-> Đã ghi file báo cáo phân tích: {txt_file}")

    temp_dir.cleanup()


if __name__ == "__main__":
    run_profiler(10)
