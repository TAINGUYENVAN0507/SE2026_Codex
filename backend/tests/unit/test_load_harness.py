"""Harness tải (AI-19): client không được dùng lại kết nối đúng lúc uvicorn đóng nó.

Ở 247 client có 6/6.669 upload lỗi RemoteProtocolError; các lỗi có chi tiết xảy ra khi kết nối
đã rảnh 4,94 đến 5,00 s (docs/evidence/load-247/after-2026-11-10/keepalive/). httpx mặc định giữ
kết nối rảnh 5,0 s, bằng đúng timeout keep-alive mặc định của uvicorn, nên hai bên có thể cùng
lúc: server đóng, client gửi. Thử riêng lẻ không tái hiện được (0/42), nên test chặn điều kiện
gây race thay vì tái hiện nó.
"""

import importlib.util
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest
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


# Ghim CPU (AD-018, AI-19): tách máy sinh tải khỏi server khi đo 247 client trên một máy.


def test_parse_cpus_reads_ranges_and_lists(monkeypatch):
    harness = load_harness()
    monkeypatch.setattr(harness.os, "cpu_count", lambda: 12)
    assert harness.parse_cpus("0-3,6-9") == {0, 1, 2, 3, 6, 7, 8, 9}
    assert harness.parse_cpus("4,5,10,11") == {4, 5, 10, 11}
    assert harness.parse_cpus(None) is None
    assert harness.parse_cpus("") is None


def test_parse_cpus_rejects_reversed_or_missing_cpus(monkeypatch):
    harness = load_harness()
    monkeypatch.setattr(harness.os, "cpu_count", lambda: 4)
    with pytest.raises(ValueError, match="ngược"):
        harness.parse_cpus("3-1")
    with pytest.raises(ValueError, match="không có"):
        harness.parse_cpus("0-5")


def test_server_and_client_cpus_must_not_overlap():
    harness = load_harness()
    with pytest.raises(ValueError, match="trùng CPU \\[3\\]"):
        harness.check_disjoint({0, 1, 2, 3}, {3, 4})
    harness.check_disjoint({0, 1}, {2, 3})
    harness.check_disjoint(None, {2, 3})


@pytest.mark.skipif(not hasattr(os, "sched_setaffinity"), reason="chỉ Linux có sched_setaffinity")
def test_pinned_process_and_its_children_run_only_on_the_given_cpu():
    """API chạy qua `uv run uvicorn --workers N`: worker của uvicorn là cháu của Popen, nên
    ghim phải được kế thừa xuống process cháu."""
    harness = load_harness()
    cpu = min(os.sched_getaffinity(0))
    show = "import os;print(sorted(os.sched_getaffinity(0)))"
    grandchild = f"import subprocess,sys;subprocess.run([sys.executable,'-c',{show!r}])"
    out = subprocess.run(
        [sys.executable, "-c", f"{show};{grandchild}"],
        preexec_fn=harness.pin_to({cpu}),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert out == [f"[{cpu}]", f"[{cpu}]"]
    assert harness.pin_to(None) is None


def test_run_clients_without_clients_does_not_wait_for_uploads():
    """Pha upload kết thúc khi upload cuối xong; không có client thì không được chờ 600 s."""
    harness = load_harness()
    rows, errors, idle, detail, cpu = harness.run_clients(
        [], "http://127.0.0.1:1", Path("khong-co.wav"), 0, 0.0, lambda: None, lambda: None
    )
    assert (rows, errors, idle, detail) == ([], [], [], [])
    assert set(cpu) == {"cpu_s", "wall_s"}
    assert cpu["wall_s"] < 5


A = "0004a7b3-4ce7-4846-adb6-ef15c6a75c80"
B = "0006dd31-5530-4095-a18a-2771ce8f4184"
OTHER = "00084d5c-4f2b-4c9e-8a43-2d7e9c1f0b11"


def make_meeting_dirs(storage: Path, ids: list[str], subs=("audio", "artifacts")) -> None:
    for i in ids:
        for sub in subs:
            (storage / sub / i).mkdir(parents=True)
            (storage / sub / i / "original.wav").write_bytes(b"RIFF")


def test_remove_run_files_deletes_only_the_meetings_of_the_run(tmp_path):
    """Harness không dọn file sau mỗi lượt nên thư mục lưu của máy đo lên 22.947 thư mục (11-16)."""
    harness = load_harness()
    make_meeting_dirs(tmp_path, [A, OTHER])
    make_meeting_dirs(tmp_path, [B], subs=("audio",))
    assert harness.remove_run_files(tmp_path, [A, B]) == 3
    assert sorted(p.name for p in (tmp_path / "audio").iterdir()) == [OTHER]
    assert sorted(p.name for p in (tmp_path / "artifacts").iterdir()) == [OTHER]
    assert harness.count_dirs(tmp_path / "audio") == 1


@pytest.mark.parametrize("bad", ["..", "../audio", "", A.upper(), A.replace("-", ""), f"{{{A}}}"])
def test_remove_run_files_checks_every_id_before_deleting(tmp_path, bad):
    """Một id không đúng dạng UUID của DB thì không xóa gì, kể cả các id hợp lệ đứng trước."""
    harness = load_harness()
    make_meeting_dirs(tmp_path, [A])
    with pytest.raises(ValueError, match="không phải UUID"):
        harness.remove_run_files(tmp_path, [A, bad])
    assert (tmp_path / "audio" / A / "original.wav").exists()
    assert (tmp_path / "artifacts" / A).is_dir()


def test_remove_run_files_does_not_follow_a_symlinked_meeting_dir(tmp_path):
    harness = load_harness()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    (tmp_path / "store" / "audio").mkdir(parents=True)
    (tmp_path / "store" / "audio" / A).symlink_to(outside, target_is_directory=True)
    assert harness.remove_run_files(tmp_path / "store", [A]) == 0
    assert (outside / "keep.txt").exists()


def test_count_dirs_counts_subdirectories_only(tmp_path):
    harness = load_harness()
    assert harness.count_dirs(tmp_path / "chua-co") == 0
    make_meeting_dirs(tmp_path, [A, B], subs=("audio",))
    (tmp_path / "audio" / "note.txt").write_text("x")
    assert harness.count_dirs(tmp_path / "audio") == 2


def test_harness_storage_is_where_the_app_writes():
    """Harness xóa trong đúng thư mục API và worker ghi (LocalStorage mặc định)."""
    from app.services.storage.local import LocalStorage

    assert LocalStorage().base_dir == load_harness().STORAGE
