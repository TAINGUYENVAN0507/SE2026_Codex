"""Kiểm thử giới hạn kích thước log cho toàn bộ services trong docker-compose.yml.

Thuộc AD-018, BE-16.
Mọi container (db, api, worker, web) phải có cấu hình logging:
- driver: "json-file"
- max-size: "10m"
- max-file: "3"

Đảm bảo log container được xoay vòng theo kích thước tệp (30MB tối đa),
không tăng trưởng vô hạn trên đĩa và không phụ thuộc chu kỳ 28 ngày.
"""

from pathlib import Path

import yaml


def test_all_compose_services_have_bounded_json_logging() -> None:
    """Tất cả service trong docker-compose.yml phải có logging json-file giới hạn dung lượng."""
    compose_path = Path(__file__).resolve().parents[3] / "docker-compose.yml"
    assert compose_path.exists(), f"Không tìm thấy file {compose_path}"

    with compose_path.open("r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    assert "services" in compose_data, "docker-compose.yml phải chứa khóa 'services'"
    services = compose_data["services"]
    assert len(services) >= 4, (
        "docker-compose.yml phải chứa ít nhất 4 services (db, api, worker, web)"
    )

    for service_name, config in services.items():
        assert "logging" in config, f"Service '{service_name}' thiếu cấu hình 'logging'"
        logging_cfg = config["logging"]
        driver = logging_cfg.get("driver")
        assert driver == "json-file", (
            f"Service '{service_name}' phải dùng logging driver 'json-file', nhận: {driver}"
        )
        options = logging_cfg.get("options", {})
        max_size = options.get("max-size")
        assert max_size == "10m", (
            f"Service '{service_name}' phải có max-size là '10m', nhận: {max_size}"
        )
        max_file = options.get("max-file")
        assert max_file == "3", (
            f"Service '{service_name}' phải có max-file là '3', nhận: {max_file}"
        )
