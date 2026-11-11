"""Harness tải (AI-19): client không được dùng lại kết nối đúng lúc uvicorn đóng nó.

Ở 247 client có 6/6.669 upload lỗi RemoteProtocolError; các lỗi có chi tiết xảy ra khi kết nối
đã rảnh 4,94 đến 5,00 s (docs/evidence/load-247/after-2026-11-10/keepalive/). httpx mặc định giữ
kết nối rảnh 5,0 s, bằng đúng timeout keep-alive mặc định của uvicorn, nên hai bên có thể cùng
lúc: server đóng, client gửi. Thử riêng lẻ không tái hiện được (0/42), nên test chặn điều kiện
gây race thay vì tái hiện nó.
"""

import importlib.util
import inspect
from pathlib import Path

import uvicorn.config

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "load_vt018.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("load_vt018", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def uvicorn_keep_alive() -> float:
    params = inspect.signature(uvicorn.config.Config.__init__).parameters
    return params["timeout_keep_alive"].default


def test_client_drops_idle_connections_well_before_uvicorn_does():
    harness = load_harness()
    with harness.make_client("http://127.0.0.1:1") as client:
        expiry = client._transport._pool._keepalive_expiry
    # Chừa ít nhất 1 s để lịch của server trễ dưới tải cũng không chạm tới.
    assert expiry is not None
    assert expiry <= uvicorn_keep_alive() - 1


def test_harness_does_not_shorten_uvicorn_keep_alive():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--timeout-keep-alive" not in source
