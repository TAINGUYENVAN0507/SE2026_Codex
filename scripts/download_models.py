"""Tải trước model của pipeline vào cache (AI-16). Chạy bằng môi trường của pipeline:

    cd pipeline && uv run python ../scripts/download_models.py [--check]

Chỉ gọi `python -m meeting_pipeline download-models`; chi tiết ở `pipeline/meeting_pipeline/models.py`.
"""

import sys

from meeting_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["download-models", *sys.argv[1:]]))
