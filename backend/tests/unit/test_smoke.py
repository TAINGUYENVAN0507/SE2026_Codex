"""Smoke test cơ bản để xác nhận import package app và môi trường chạy."""

import app


def test_import_app():
    """Kiểm tra import thành công package app và thuộc tính version."""
    assert app.__version__ == "0.1.0"
