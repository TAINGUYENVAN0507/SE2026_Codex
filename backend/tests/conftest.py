"""Cấu hình pytest và các fixture dùng chung cho kiểm thử backend."""

import os
import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings


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


@pytest.fixture(scope="session", autouse=True)
def guard_no_real_appdata_leak() -> Generator[None, None, None]:
    """Bảo vệ appdata: không test nào được ghi thư mục vào appdata/audio thật (BE-16)."""
    appdata_audio = Path(__file__).resolve().parent.parent / "appdata" / "audio"
    before = set(appdata_audio.iterdir()) if appdata_audio.exists() else set()
    yield
    after = set(appdata_audio.iterdir()) if appdata_audio.exists() else set()
    new_dirs = after - before
    # Dọn dẹp thư mục rác do test tạo ra để không làm ô nhiễm môi trường chạy tiếp theo
    for d in new_dirs:
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    leaked = [d.name for d in new_dirs]
    assert not new_dirs, (
        f"Phát hiện test ghi trực tiếp vào backend/appdata/audio thật: {leaked}. "
        "Test phải sử dụng storage tạm (tmp_path)!"
    )
