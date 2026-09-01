from __future__ import annotations

import socket
from pathlib import Path

import pytest

import scripts.jp_assist_core as core
from scripts.jp_assist_core import DataStore, RemoteUpdater


PUBLIC_URL = "https://93.184.216.34/tags.csv"
VALID_CSV = b"tag,category,count\nupdated,0,1\n"


class FakeResponse:
    def __init__(self, *, data: bytes = b"", chunks=None, headers=None, status_code: int = 200):
        self.data = data
        self.chunks = list(chunks) if chunks is not None else [data]
        self.headers = headers or {}
        self.status_code = status_code
        self.iterated = False
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024):
        self.iterated = True
        yield from self.chunks

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


class ValidSession:
    def __init__(self, body: bytes = VALID_CSV):
        self.body = body
        self.head_calls = []
        self.get_calls = []
        self.get_response = None

    def head(self, url, allow_redirects=False, timeout=10):
        self.head_calls.append((url, allow_redirects))
        return FakeResponse(headers={"ETag": '"v1"', "Content-Length": str(len(self.body))})

    def get(self, url, allow_redirects=False, stream=True, timeout=(10, 90)):
        self.get_calls.append((url, allow_redirects))
        self.get_response = FakeResponse(data=self.body, headers={"Content-Length": str(len(self.body))})
        return self.get_response


class NoNetworkSession:
    def head(self, *args, **kwargs):
        raise AssertionError("network access must not start")

    def get(self, *args, **kwargs):
        raise AssertionError("network access must not start")


@pytest.mark.parametrize(
    "url",
    (
        "http://localhost/tags.csv",
        "http://127.0.0.1/tags.csv",
        "http://10.1.2.3/tags.csv",
        "http://172.16.0.1/tags.csv",
        "http://192.168.1.1/tags.csv",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/tags.csv",
    ),
)
def test_remote_update_rejects_local_and_private_destinations(tmp_path: Path, url: str) -> None:
    updater = RemoteUpdater(DataStore(tmp_path / "tags"))
    with pytest.raises(ValueError):
        updater.update(NoNetworkSession(), url, "remote.csv")


def test_remote_update_rejects_credentialed_urls(tmp_path: Path) -> None:
    updater = RemoteUpdater(DataStore(tmp_path / "tags"))
    with pytest.raises(ValueError, match="credentials"):
        updater.update(NoNetworkSession(), "https://user:pass@93.184.216.34/tags.csv", "remote.csv")


def test_remote_update_allows_public_hostname_resolution(monkeypatch) -> None:
    def public_address(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(core.socket, "getaddrinfo", public_address)
    assert RemoteUpdater._validate_remote_url("https://example.com/tags.csv") == "https://example.com/tags.csv"


def test_remote_update_rejects_hostname_resolving_to_private_address(monkeypatch) -> None:
    def private_address(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.5", 443))]

    monkeypatch.setattr(core.socket, "getaddrinfo", private_address)
    with pytest.raises(ValueError, match="private, local, or reserved"):
        RemoteUpdater._validate_remote_url("https://internal.example/tags.csv")


def test_public_to_private_redirect_is_rejected_before_next_request(tmp_path: Path) -> None:
    class RedirectSession(ValidSession):
        def head(self, url, allow_redirects=False, timeout=10):
            self.head_calls.append((url, allow_redirects))
            return FakeResponse(status_code=302, headers={"Location": "http://127.0.0.1/tags.csv"})

    session = RedirectSession()
    updater = RemoteUpdater(DataStore(tmp_path / "tags"))
    result = updater.update(session, PUBLIC_URL, "remote.csv")
    assert result["updated"] is False
    assert "private, local, or reserved" in result["error"]
    assert session.head_calls == [(PUBLIC_URL, False)]
    assert session.get_calls == []


def test_oversized_content_length_is_rejected_before_get_body(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(core, "MAX_REMOTE_CSV_BYTES", 32)

    class OversizedSession(ValidSession):
        def head(self, url, allow_redirects=False, timeout=10):
            self.head_calls.append((url, allow_redirects))
            return FakeResponse(headers={"Content-Length": "33"})

    store = DataStore(tmp_path / "tags")
    target = store.tag_dir / "remote.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original", encoding="utf-8")
    session = OversizedSession()
    result = RemoteUpdater(store).update(session, PUBLIC_URL, target.name)
    assert result["updated"] is False
    assert target.read_text(encoding="utf-8") == "original"
    assert session.get_calls == []


def test_get_content_length_is_rejected_without_iterating_body(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(core, "MAX_REMOTE_CSV_BYTES", 32)

    class GetOversizedSession(ValidSession):
        def head(self, url, allow_redirects=False, timeout=10):
            raise RuntimeError("HEAD unsupported")

        def get(self, url, allow_redirects=False, stream=True, timeout=(10, 90)):
            self.get_response = FakeResponse(data=VALID_CSV, headers={"Content-Length": "33"})
            return self.get_response

    session = GetOversizedSession()
    result = RemoteUpdater(DataStore(tmp_path / "tags")).update(session, PUBLIC_URL, "remote.csv")
    assert result["updated"] is False
    assert session.get_response is not None
    assert session.get_response.iterated is False


def test_stream_limit_preserves_existing_target_and_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(core, "MAX_REMOTE_CSV_BYTES", 32)

    class StreamingSession(ValidSession):
        def head(self, url, allow_redirects=False, timeout=10):
            return FakeResponse()

        def get(self, url, allow_redirects=False, stream=True, timeout=(10, 90)):
            return FakeResponse(chunks=[b"tag,category,count\n", b"x" * 20])

    store = DataStore(tmp_path / "tags")
    target = store.tag_dir / "remote.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original", encoding="utf-8")
    cache_clears = []
    monkeypatch.setattr(store, "clear_cache", lambda: cache_clears.append(True))
    result = RemoteUpdater(store).update(StreamingSession(), PUBLIC_URL, target.name)
    assert result["updated"] is False
    assert target.read_text(encoding="utf-8") == "original"
    assert not target.with_suffix(".csv.download").exists()
    assert cache_clears == []


def test_valid_download_atomically_replaces_target(tmp_path: Path, monkeypatch) -> None:
    store = DataStore(tmp_path / "tags")
    target = store.tag_dir / "remote.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original", encoding="utf-8")
    replace_calls = []
    original_replace = core.os.replace

    def record_replace(source, destination):
        replace_calls.append((Path(source), Path(destination)))
        return original_replace(source, destination)

    monkeypatch.setattr(core.os, "replace", record_replace)
    result = RemoteUpdater(store).update(ValidSession(), PUBLIC_URL, target.name)
    assert result["updated"] is True
    assert target.read_bytes() == VALID_CSV
    assert any(source.name == "remote.csv.download" and destination == target for source, destination in replace_calls)
    assert not target.with_suffix(".csv.download").exists()
