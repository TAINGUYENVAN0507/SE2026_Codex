"""Cấu hình pytest và các fixture dùng chung cho kiểm thử backend."""

import atexit
import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.services.storage import get_storage

# Đặt STORAGE_DIR sang thư mục tạm cho cả phiên test (BE-16)
_SESSION_TMP_STORAGE = tempfile.mkdtemp(prefix="codex_test_storage_")
os.environ["STORAGE_DIR"] = _SESSION_TMP_STORAGE
atexit.register(lambda: shutil.rmtree(_SESSION_TMP_STORAGE, ignore_errors=True))

get_settings.cache_clear()
get_storage.cache_clear()


def get_alembic_config(db_url: str) -> Config:
    """Tạo cấu hình Alembic cho database kiểm thử."""
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.attributes["skip_logging_config"] = True
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _check_postgres_connection(db_url: str) -> bool:
    """Kiểm tra kết nối tới cơ sở dữ liệu PostgreSQL."""
    if not db_url.startswith("postgresql"):
        return False
    try:
        connect_args = {"connect_timeout": 1} if "psycopg" in db_url else {}
        test_engine = create_engine(db_url, connect_args=connect_args)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        return True
    except Exception:
        return False


def check_postgres_or_skip(db_url: str | None = None) -> str:
    """Kiểm tra PostgreSQL; skip nếu ở máy local hoặc fail nếu trên CI."""
    settings = get_settings()
    url = db_url or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    if not _check_postgres_connection(url):
        is_ci = os.environ.get("CI", "").strip().lower() in ("true", "1")
        if is_ci:
            pytest.fail("cần Postgres: docker compose up -d db")
        pytest.skip("cần Postgres: docker compose up -d db")
    return url


@pytest.fixture
def require_postgres() -> str:
    """Đảm bảo kết nối PostgreSQL sẵn sàng; skip ở máy local hoặc fail trên CI."""
    return check_postgres_or_skip()


@pytest.fixture
def db_session(require_postgres: str) -> Generator[Session, None, None]:
    """Fixture khởi tạo database sạch trên Postgres, chạy migration và cấp Session."""
    cfg = get_alembic_config(require_postgres)
    command.upgrade(cfg, "head")

    engine = create_engine(require_postgres)
    session = Session(engine)

    try:
        yield session
    finally:
        session.close()
        command.downgrade(cfg, "base")
        engine.dispose()


def snapshot_directory_entries(dir_path: Path) -> set[Path]:
    """Lấy snapshot danh sách các file/thư mục hiện có."""
    return set(dir_path.iterdir()) if dir_path.exists() else set()


def check_directory_leak(dir_path: Path, before: set[Path]) -> list[str]:
    """Kiểm tra và báo lỗi nếu có thư mục mới xuất hiện so với snapshot ban đầu.

    Chỉ báo lỗi và liệt kê tên các thư mục bị rò rỉ, TUYỆT ĐỐI KHÔNG xóa bất kỳ file nào (BE-16),
    nhằm tránh xóa nhầm dữ liệu của API dev hay load harness đang chạy đồng thời.
    """
    after = snapshot_directory_entries(dir_path)
    new_entries = sorted(after - before)
    if new_entries:
        leaked = [p.name for p in new_entries]
        raise AssertionError(
            f"Phát hiện test ghi trực tiếp vào backend/appdata/audio thật: {leaked}. "
            "Test phải sử dụng storage tạm (tmp_path)!"
        )
    return []


@pytest.fixture(scope="session", autouse=True)
def guard_no_real_appdata_leak() -> Generator[None, None, None]:
    """Bảo vệ appdata: không test nào được ghi thư mục vào appdata/audio thật (BE-16)."""
    appdata_audio = Path(__file__).resolve().parent.parent / "appdata" / "audio"
    before = snapshot_directory_entries(appdata_audio)
    yield
    check_directory_leak(appdata_audio, before)
