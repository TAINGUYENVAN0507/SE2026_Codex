import hashlib
import io
import json
import tarfile
from pathlib import Path

import download
import pytest


def make_source(tmp_path: Path, content: bytes, sha: str | None, extract=False, name="a.tsv"):
    src = tmp_path / "remote" / name
    src.parent.mkdir(exist_ok=True)
    src.write_bytes(content)
    return {
        "dataset": "test",
        "description": "test",
        "url": src.as_uri(),
        "sha256": sha,
        "size_bytes": len(content),
        "license": "CC0",
        "extract": extract,
    }


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_download_verifies_checksum(tmp_path):
    body = "id\tfile\tmặt khác\n".encode()
    sources = {"s": make_source(tmp_path, body, sha(body))}
    dest = download.download("s", sources, tmp_path / "raw")
    assert dest.read_bytes() == body
    # Lần hai không tải lại.
    assert download.download("s", sources, tmp_path / "raw") == dest


def test_checksum_mismatch_removes_file(tmp_path):
    sources = {"s": make_source(tmp_path, b"abc", "0" * 64)}
    with pytest.raises(download.ChecksumError):
        download.download("s", sources, tmp_path / "raw")
    assert list((tmp_path / "raw" / "s").iterdir()) == []


def test_missing_checksum_requires_pin(tmp_path):
    sources = {"s": make_source(tmp_path, b"abc", None)}
    with pytest.raises(download.ChecksumError):
        download.download("s", sources, tmp_path / "raw")
    download.download("s", sources, tmp_path / "raw", pin=True)
    assert sources["s"]["sha256"] == sha(b"abc")


def test_main_pin_writes_sources_file(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"s": make_source(tmp_path, b"xyz", None)}))
    code = download.main(["s", "--pin", "--sources", str(path), "--raw-dir", str(tmp_path / "r")])
    assert code == 0
    assert json.loads(path.read_text())["s"]["sha256"] == sha(b"xyz")


def tar_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_extracts_archive(tmp_path):
    body = tar_bytes({"test/1.wav": b"RIFF"})
    sources = {"s": make_source(tmp_path, body, sha(body), extract=True, name="a.tar.gz")}
    dest = download.download("s", sources, tmp_path / "raw")
    assert (dest.parent / "test" / "1.wav").read_bytes() == b"RIFF"


def test_rejects_path_traversal_in_archive(tmp_path):
    body = tar_bytes({"../escape.txt": b"x"})
    sources = {"s": make_source(tmp_path, body, sha(body), extract=True, name="a.tar.gz")}
    with pytest.raises(tarfile.FilterError):
        download.download("s", sources, tmp_path / "raw")
    assert not (tmp_path / "raw" / "escape.txt").exists()


def test_committed_sources_are_complete():
    sources = download.load_sources()
    assert sources, "sources.json rỗng"
    for sid, entry in sources.items():
        assert entry["url"].startswith("https://"), sid
        assert len(entry["sha256"]) == 64, sid
        assert entry["license"], sid


def test_unknown_source_returns_2(tmp_path):
    assert download.main(["nope"]) == 2
