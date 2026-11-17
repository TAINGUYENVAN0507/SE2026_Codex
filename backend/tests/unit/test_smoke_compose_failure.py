"""Kiểm thử độ tin cậy của smoke_compose: lỗi khi không đọc được log container.

Thuộc AD-018, BE-16.
Phát hiện P2 từ review PR #61 của Member A:
Khi docker compose logs trả về return code != 0 hoặc thiếu docker CLI (FileNotFoundError),
smoke test trước đây chỉ in [CẢNH BÁO] và vẫn báo thành công.
Test này xác nhận:
1. subprocess.run trả returncode=1 -> run_smoke phải raise RuntimeError.
2. subprocess.run ném FileNotFoundError -> run_smoke phải raise RuntimeError.
3. Khi truyền cờ skip_docker_logs=True -> cho phép bỏ qua khi test cục bộ không có Docker.
"""

from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from scripts import smoke_compose


@pytest.fixture
def mock_smoke_env():
    """Mock HTTP calls và user creation để kiểm tra xử lý log container của run_smoke."""
    with (
        patch("scripts.smoke_compose.wait_for_api"),
        patch("scripts.smoke_compose.create_synthetic_user"),
        patch("httpx.Client") as mock_client_cls,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Mock login response
        mock_login_res = MagicMock()
        mock_login_res.status_code = 200
        mock_client.post.return_value = mock_login_res

        # Mock upload response
        mock_upload_res = MagicMock()
        mock_upload_res.status_code = 201
        mock_upload_res.json.return_value = {
            "meeting": {"id": "mock-meeting-id"},
            "job": {"id": "mock-job-id"},
        }

        # Mock poll job response (succeeded)
        mock_poll_res = MagicMock()
        mock_poll_res.status_code = 200
        mock_poll_res.json.return_value = {"status": "succeeded", "stage": "summarize"}

        # Mock metrics response
        mock_metrics_res = MagicMock()
        mock_metrics_res.status_code = 200
        mock_metrics_res.text = "pipeline_stage_duration_seconds_count 1.0\n"

        # Mock export responses
        mock_export_res = MagicMock()
        mock_export_res.status_code = 200
        mock_export_res.text = "export content"

        # Mock delete responses
        mock_del_res = MagicMock()
        mock_del_res.status_code = 204

        def client_post(url, **kwargs):
            if "/auth/login" in url:
                return mock_login_res
            if "/meetings" in url:
                return mock_upload_res
            return mock_login_res

        mock_search_res = MagicMock()
        mock_search_res.status_code = 200
        mock_search_res.json.return_value = {
            "items": [{"id": "mock-meeting-id"}],
            "total": 1,
        }

        def client_get(url, **kwargs):
            if "/export" in url:
                return mock_export_res
            if "/meetings" in url:
                return mock_search_res
            if "/jobs/" in url:
                return mock_poll_res
            if "/metrics" in url:
                return mock_metrics_res
            return mock_poll_res

        def client_delete(url, **kwargs):
            return mock_del_res

        mock_client.post.side_effect = client_post
        mock_client.get.side_effect = client_get
        mock_client.delete.side_effect = client_delete

        yield


def test_smoke_compose_fails_when_docker_logs_return_nonzero(mock_smoke_env):
    """Khi docker compose logs trả về mã lỗi != 0, run_smoke phải ném RuntimeError (AD-018)."""
    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value = CompletedProcess(
            args=["docker", "compose", "logs", "api", "worker"],
            returncode=1,
            stdout="",
            stderr="cannot read compose logs: daemon unreachable",
        )

        with pytest.raises(RuntimeError, match="Không lấy được log qua docker compose"):
            smoke_compose.run_smoke("http://localhost:8000", timeout_sec=5)


def test_smoke_compose_fails_when_docker_cli_missing(mock_smoke_env):
    """Khi thiếu docker CLI (FileNotFoundError), run_smoke phải ném RuntimeError (AD-018)."""
    with patch("subprocess.run") as mock_subproc:
        mock_subproc.side_effect = FileNotFoundError("No such file or directory: 'docker'")

        with pytest.raises(RuntimeError, match="Không tìm thấy docker CLI"):
            smoke_compose.run_smoke("http://localhost:8000", timeout_sec=5)


def test_smoke_compose_allows_skipping_docker_logs_with_flag(mock_smoke_env):
    """Khi có cờ skip_docker_logs=True, run_smoke bỏ qua kiểm tra log container mà không fail."""
    with patch("subprocess.run") as mock_subproc:
        mock_subproc.side_effect = FileNotFoundError("docker not found")

        # Phải chạy trót lọt không ném ngoại lệ
        smoke_compose.run_smoke("http://localhost:8000", timeout_sec=5, skip_docker_logs=True)


def test_smoke_compose_searches_by_canary_title(mock_smoke_env):
    """Smoke compose gọi GET /meetings?q=<canary_title> và xác thực meeting (AD-018, BE-19)."""
    with patch("subprocess.run") as mock_subproc:
        mock_subproc.return_value = CompletedProcess(
            args=["docker", "compose", "logs", "api", "worker"],
            returncode=0,
            stdout="clean logs without canary",
            stderr="",
        )
        smoke_compose.run_smoke("http://localhost:8000", timeout_sec=5)
