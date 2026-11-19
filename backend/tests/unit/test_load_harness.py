"""Harness tải (AI-19): client không được dùng lại kết nối đúng lúc uvicorn đóng nó.

Ở 247 client có 6/6.669 upload lỗi RemoteProtocolError; các lỗi có chi tiết xảy ra khi kết nối
đã rảnh 4,94 đến 5,00 s (docs/evidence/load-247/after-2026-11-10/keepalive/). httpx mặc định giữ
kết nối rảnh 5,0 s, bằng đúng timeout keep-alive mặc định của uvicorn, nên hai bên có thể cùng
lúc: server đóng, client gửi. Thử riêng lẻ không tái hiện được (0/42), nên test chặn điều kiện
gây race thay vì tái hiện nó.
"""

import importlib.util
import inspect
import json
import os
import subprocess
import sys
import time
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
    try:
        (tmp_path / "store" / "audio" / A).symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("máy không có quyền tạo symlink (Windows cần Developer Mode)")
    assert harness.remove_run_files(tmp_path / "store", [A]) == 0
    assert (outside / "keep.txt").exists()


def test_count_dirs_counts_subdirectories_only(tmp_path):
    harness = load_harness()
    assert harness.count_dirs(tmp_path / "chua-co") == 0
    make_meeting_dirs(tmp_path, [A, B], subs=("audio",))
    (tmp_path / "audio" / "note.txt").write_text("x")
    assert harness.count_dirs(tmp_path / "audio") == 2


def test_harness_storage_is_where_the_app_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Harness xóa trong đúng thư mục API và worker ghi (LocalStorage mặc định khi không đổi)."""
    from app.core.config import Settings
    from app.services.storage.local import LocalStorage

    monkeypatch.delenv("STORAGE_DIR", raising=False)
    default_settings = Settings()
    monkeypatch.setattr("app.services.storage.local.get_settings", lambda: default_settings)
    assert LocalStorage().base_dir == load_harness().STORAGE


BUSY = """
import subprocess, sys, threading, time


def spin(sec):
    end = time.perf_counter() + sec
    while time.perf_counter() < end:
        pass


if sys.argv[1] == "parent":
    child = subprocess.Popen([sys.executable, __file__, "thread"])
    spin(2.5)  # luồng chính bận
    child.wait()
else:
    t = threading.Thread(target=spin, args=(2.5,))  # luồng phụ bận, luồng chính chờ
    t.start()
    t.join()
"""


def test_stat_fields_survive_spaces_and_parens_in_the_process_name():
    harness = load_harness()
    fields = harness.stat_fields("4242 (a b) c)) S 17 4242 " + " ".join(["0"] * 8) + " 30 12 0 0")
    assert fields[0] == "S"
    assert fields[1] == "17"
    assert int(fields[11]) + int(fields[12]) == 42


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="cần /proc (Linux)")
def test_cpu_snapshot_follows_children_and_separates_the_main_thread(tmp_path):
    """Event loop của uvicorn chạy ở luồng chính; endpoint `def` chạy ở threadpool. Số của luồng
    chính phải là của riêng luồng đó, và process con (worker của --workers N) phải được đếm."""
    harness = load_harness()
    script = tmp_path / "busy.py"
    script.write_text(BUSY)
    proc = subprocess.Popen([sys.executable, str(script), "parent"])
    try:
        time.sleep(0.5)
        before = harness.cpu_snapshot(proc.pid)
        t0 = time.perf_counter()
        time.sleep(1.0)
        after = harness.cpu_snapshot(proc.pid)
        wall = time.perf_counter() - t0
    finally:
        proc.wait(timeout=15)
    rows = {r["depth"]: r for r in harness.cpu_busy(before, after, wall)}
    assert set(rows) == {0, 1}
    assert rows[0]["main_thread_cpus"] > 0.4
    assert rows[1]["process_cpus"] > 0.4
    assert rows[1]["main_thread_cpus"] < 0.2


def test_cpu_busy_skips_processes_that_started_after_the_first_snapshot():
    harness = load_harness()
    tick = harness.CLK_TCK
    before = {1: {"comm": "python", "depth": 0, "total": 0, "main": 0}}
    after = {
        1: {"comm": "python", "depth": 0, "total": 2 * tick, "main": tick},
        2: {"comm": "python", "depth": 1, "total": 5 * tick, "main": 5 * tick},
    }
    assert harness.cpu_busy(before, after, 2.0) == [
        {"comm": "python", "depth": 0, "process_cpus": 1.0, "main_thread_cpus": 0.5}
    ]


def test_upload_verdict_is_separate_from_the_all_requests_verdict():
    """247 client, 1.235 poll nhanh: 49 upload chậm là 20 % upload nhưng chỉ 3 % mọi request, nên
    p95 gộp đạt còn p95 upload không (như lượt p1-2 ngày 11-16)."""
    harness = load_harness()
    uploads = [("create", 201, 1.0)] * 198 + [("create", 201, 2.4)] * 49
    rows = uploads + [("poll", 200, 0.1)] * 1235
    assert harness.verdicts(rows, [], 2.0) == {"all": "PASS", "upload": "FAIL"}
    fast = [("create", 201, 1.0)] * 247 + [("poll", 200, 0.1)] * 1235
    assert harness.verdicts(fast, [], 2.0) == {"all": "PASS", "upload": "PASS"}


def test_upload_verdict_fails_on_upload_errors_without_a_row():
    harness = load_harness()
    rows = [("create", 201, 1.0)] * 10
    assert harness.verdicts(rows, [("create", "RemoteProtocolError")], 2.0)["upload"] == "FAIL"
    assert harness.verdicts(rows, [("poll", 500)], 2.0) == {"all": "FAIL", "upload": "PASS"}
    assert harness.verdicts([], [], 2.0) == {"all": "FAIL", "upload": "FAIL"}


def _app_line(path: str) -> str:
    return json.dumps({"message": "HTTP request completed", "path": path, "status_code": 200})


def test_api_log_stats_counts_app_and_uvicorn_access(tmp_path: Path) -> None:
    log = tmp_path / "api.stdout"
    log.write_text(
        "\n".join(
            [
                _app_line("/api/v1/meetings"),
                _app_line("/api/v1/jobs/abc"),
                '{"message": "other"}',
                'INFO:     127.0.0.1:5 - "GET /api/v1/jobs/abc HTTP/1.1" 200 OK',
                "",
            ]
        ),
        encoding="utf-8",
    )
    stats = load_harness().api_log_stats(log)
    assert stats == {
        "lines": 4,
        "app_access": 2,
        "uvicorn_access": 1,
        "with_query_string": 0,
    }


@pytest.mark.parametrize(
    "line",
    [
        _app_line("/api/v1/meetings?q=CANARY"),
        'INFO:     127.0.0.1:5 - "GET /api/v1/meetings?q=CANARY HTTP/1.1" 401 Unauthorized',
    ],
)
def test_api_log_stats_flags_a_query_string(tmp_path: Path, line: str) -> None:
    log = tmp_path / "api.stdout"
    log.write_text(line + "\n", encoding="utf-8")
    assert load_harness().api_log_stats(log)["with_query_string"] == 1


def test_search_terms_rotate_the_wildcards_and_the_client_title() -> None:
    harness = load_harness()
    assert harness.search_terms(0, 4) == ["%", "_", "100%", "Tải 0"]
    assert harness.search_terms(5, 2) == ["_", "100%"]
    assert harness.search_terms(3, 0) == []


@pytest.mark.parametrize(
    ("term", "total", "ok"),
    [("%", 0, True), ("%", 3, False), ("_", 1, False), ("100%", 0, True), ("Tải 7", 1, True)],
)
def test_search_ok_wants_no_hit_for_wildcards_and_a_hit_for_the_title(
    term: str, total: int, ok: bool
) -> None:
    assert load_harness().search_ok(term, total) is ok


def _fake_api(search_total):
    """API giả cho client_run: total của tìm kiếm do search_total(q) quyết định."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/auth/login":
            return httpx.Response(200, json={})
        if path == "/api/v1/meetings" and request.method == "POST":
            return httpx.Response(201, json={"job": {"id": "j1"}})
        if path == "/api/v1/meetings":
            q = request.url.params["q"]
            return httpx.Response(200, json={"total": search_total(q), "items": []})
        return httpx.Response(200, json={})

    return handler


@pytest.mark.parametrize(
    ("search_total", "wrong"),
    [
        (lambda q: 0 if q in ("%", "_", "100%") else 1, []),
        # Trước #67, % và _ là wildcard nên khớp mọi cuộc họp.
        (lambda q: 0 if q == "100%" else 5, [("search_wrong", "%"), ("search_wrong", "_")]),
    ],
)
def test_client_run_searches_after_upload_and_counts_wrong_results(
    monkeypatch, tmp_path: Path, search_total, wrong
) -> None:
    import threading

    import httpx

    harness = load_harness()
    transport = httpx.MockTransport(_fake_api(search_total))
    monkeypatch.setattr(
        harness, "make_client", lambda base: httpx.Client(base_url=base, transport=transport)
    )
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    ready, start = threading.Barrier(1), threading.Event()
    start.set()
    rows, errors = [], []
    harness.client_run(0, "http://api", wav, ready, start, 0, 0.0, rows, errors, [], [], searches=4)
    assert [k for k, _, _ in rows] == ["create", "search", "search", "search", "search"]
    assert errors == wrong
