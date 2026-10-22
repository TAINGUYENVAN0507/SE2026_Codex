"""Router cho cấu hình hệ thống (Config)."""

import json
from pathlib import Path

from fastapi import APIRouter, status

from app.schemas.config import ConfigOut

router = APIRouter(prefix="/config", tags=["Config"])

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "contracts" / "fixtures" / "api" / "config.json"
)


def load_config_fixture() -> dict:
    """Đọc dữ liệu fixture cấu hình hệ thống."""
    if FIXTURE_PATH.is_file():
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "max_upload_mb": 200,
        "max_duration_sec": 14400,
        "allowed_extensions": [
            ".mp3",
            ".m4a",
            ".wav",
            ".aac",
            ".ogg",
            ".webm",
            ".flac",
        ],
        "export_formats": ["txt", "json", "md", "docx"],
        "llm_enabled": True,
    }


@router.get(
    "",
    response_model=ConfigOut,
    status_code=status.HTTP_200_OK,
    summary="Lấy cấu hình hệ thống",
)
def get_config() -> ConfigOut:
    """Trả về cấu hình hệ thống cho frontend (giới hạn upload, thời lượng, formats)."""
    data = load_config_fixture()
    return ConfigOut.model_validate(data)
