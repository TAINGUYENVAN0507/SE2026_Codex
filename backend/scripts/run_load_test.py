"""Load test harness for VT-017: 100 concurrent users/tasks search & pagination.

Mục tiêu kiểm chứng: 100 tác vụ đồng thời; p95 latency <= 3.0 giây.
Đo lường chi tiết: Min, Avg, p50, p90, p95, p99, Max, Throughput (req/s), Success rate.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import random
import sys
import tempfile
import time
import uuid

# Đảm bảo in unicode ra console trên Windows an toàn
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.idempotency import IdempotencyKey
from app.db.models.job import Job
from app.db.models.meeting import Meeting
from app.db.models.transcript import Speaker
from app.db.models.user import User
from app.db.session import get_db
from app.main import create_app


def setup_load_test_environment(db_file: str):
    """Khởi tạo database và nạp 200 bản ghi mẫu cho load test."""
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    tables = [
        User.__table__,
        Meeting.__table__,
        Job.__table__,
        IdempotencyKey.__table__,
        Speaker.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    # Tạo User
    user = User(
        id=str(uuid.uuid4()),
        email="load_test_user@example.com",
        display_name="Load Test User",
        password_hash="hash_load_test",
    )
    session.add(user)
    session.commit()

    # Nạp 200 bản ghi cuộc họp với đa dạng tiêu đề, trạng thái, ngày họp và nguồn
    sources = ["upload", "recording"]
    statuses = ["ready", "queued", "processing", "partial"]
    keywords = ["kiến trúc", "pipeline", "sprint planning", "review", "báo cáo", "họp tuần", "AI model"]

    for i in range(200):
        kw = random.choice(keywords)
        src = random.choice(sources)
        st = random.choice(statuses)
        day = (i % 28) + 1
        m = Meeting(
            id=str(uuid.uuid4()),
            owner_id=user.id,
            title=f"Cuộc họp {kw} số {i:03d}",
            source=src,
            status=st,
            meeting_date=f"2026-11-{day:02d}",
            version=1,
        )
        session.add(m)
    user_id = user.id
    session.commit()
    session.close()

    return engine, session_factory, user_id, user


def run_single_request(app, token, query_params: str) -> tuple[bool, float, int]:
    """Gửi 1 HTTP request và đo lường thời gian đáp ứng (latency)."""
    with TestClient(app, cookies={"session_token": token}) as client:
        t0 = time.perf_counter()
        res = client.get(f"/api/v1/meetings{query_params}")
        t1 = time.perf_counter()
        duration_sec = t1 - t0
        is_success = (res.status_code == 200) and ("items" in res.json())
        return is_success, duration_sec, res.status_code


def main():
    print("=" * 70)
    print("KIỂM CHỨNG TẢI VT-017: 100 TÁC VỤ ĐỒNG THỜI (CONCURRENT SEARCH & PAGINATION)")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        engine, session_factory, user_id, user_obj = setup_load_test_environment(tmp_db_path)
        print(f"[*] Đã nạp 200 bản ghi cuộc họp vào cơ sở dữ liệu kiểm thử: {tmp_db_path}")

        app = create_app()

        def _override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        def _override_current_user():
            db = session_factory()
            try:
                return db.get(User, user_id)
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_current_user
        token = create_access_token(user_id)

        # Chuẩn bị 100 kịch bản truy vấn thực tế khác nhau
        test_queries = [
            "?page=1&page_size=10",
            "?page=2&page_size=10&status=ready",
            "?page=1&page_size=20&sort_by=meeting_date&order=desc",
            "?page=3&page_size=5&source=upload",
            "?page=1&page_size=15&q=kiến trúc",
            "?page=2&page_size=10&q=báo cáo&sort_by=title&order=asc",
            "?page=1&page_size=10&from_date=2026-11-01&to_date=2026-11-15",
            "?page=1&page_size=25&source=recording&status=ready",
            "?page=4&page_size=10&sort_by=created_at&order=desc",
            "?page=1&page_size=50",
        ]

        tasks = [random.choice(test_queries) for _ in range(100)]

        print(f"[*] Bắt đầu thực thi đồng thời {len(tasks)} requests bằng 100 worker threads...")
        start_all = time.perf_counter()

        latencies = []
        success_count = 0

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(run_single_request, app, token, q) for q in tasks]
            for future in as_completed(futures):
                success, latency, status_code = future.result()
                latencies.append(latency)
                if success:
                    success_count += 1

        total_elapsed = time.perf_counter() - start_all

        latencies.sort()
        count = len(latencies)
        min_l = latencies[0] * 1000
        max_l = latencies[-1] * 1000
        avg_l = (sum(latencies) / count) * 1000
        p50 = latencies[int(count * 0.50)] * 1000
        p90 = latencies[int(count * 0.90)] * 1000
        p95 = latencies[int(count * 0.95)] * 1000
        p99 = latencies[int(count * 0.99)] * 1000
        throughput = count / total_elapsed

        print("-" * 70)
        print("KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG TẢI:")
        print(f"- Tổng số tác vụ đồng thời:        {count}")
        print(f"- Số request thành công:            {success_count}/{count} ({success_count/count*100:.1f}%)")
        print(f"- Tổng thời gian hoàn thành:       {total_elapsed:.3f} s")
        print(f"- Thông lượng (Throughput):         {throughput:.2f} req/s")
        print(f"- Độ trễ nhỏ nhất (Min):            {min_l:.2f} ms")
        print(f"- Độ trễ trung bình (Avg):          {avg_l:.2f} ms")
        print(f"- Median (p50):                     {p50:.2f} ms")
        print(f"- p90:                              {p90:.2f} ms")
        print(f"- p95:                              {p95:.2f} ms")
        print(f"- p99:                              {p99:.2f} ms")
        print(f"- Độ trễ lớn nhất (Max):            {max_l:.2f} ms")
        print("-" * 70)
        print(f"MỤC TIÊU BIẾN THỂ VT-017: p95 <= 3.0 s (3000 ms)")
        if p95 <= 3000:
            print(f"==> KẾT LUẬN: ĐẠT MỤC TIÊU HIỆU NĂNG (p95 = {p95:.2f} ms <= 3000 ms, vượt chuẩn {(3000-p95)/3000*100:.1f}%)")
        else:
            print(f"==> KẾT LUẬN: KHÔNG ĐẠT MỤC TIÊU HIỆU NĂNG (p95 = {p95:.2f} ms > 3000 ms)")
        print("=" * 70)

    finally:
        try:
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)
        except Exception:
            pass


if __name__ == "__main__":
    main()
