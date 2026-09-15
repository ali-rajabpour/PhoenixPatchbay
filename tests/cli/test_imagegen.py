"""patchbay image: settings lookup, both response shapes, and what must never happen."""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

import pytest

from phoenix_patchbay.cli import imagegen

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

JPEG = b"\xff\xd8\xff\xe0jpeg"
PNG = b"\x89PNG\r\n\x1a\npng"
KEY = "sk-img"


class _Provider(HTTPServer):
    bodies: list[dict[str, object]]
    download_auth: str | None = "not requested"


class _Handler(BaseHTTPRequestHandler):
    server: _Provider

    def _send(self, status: int, payload: bytes, kind: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/image.png":
            self.server.download_auth = self.headers.get("Authorization")
            self._send(200, PNG, "image/png")
        elif self.headers.get("Authorization") == f"Bearer {KEY}":
            self._send(200, json.dumps({"data": [{"id": "a"}, {"id": "b"}]}).encode())
        else:
            self._send(401, b"{}")

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.bodies.append(body)
        if self.headers.get("Authorization") != f"Bearer {KEY}":
            self._send(401, b"{}")
        elif body["model"] == "url-model":
            url = f"http://127.0.0.1:{self.server.server_port}/image.png"
            self._send(200, json.dumps({"data": [{"url": url}]}).encode())
        else:
            b64 = base64.b64encode(JPEG).decode()
            self._send(200, json.dumps({"data": [{"b64_json": b64}]}).encode())

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Provider]:
    server = _Provider(("127.0.0.1", 0), _Handler)
    server.bodies = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("PATCHBAY_HOME", str(tmp_path))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    monkeypatch.setenv("IMAGEGEN_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1/")
    monkeypatch.setenv("IMAGEGEN_MODEL", "b64-model")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.json").write_text(json.dumps({"imagegen_api_key": KEY}))
    yield server
    server.shutdown()


def test_b64_image_is_saved_under_the_suffix_of_its_bytes(
    provider: _Provider, tmp_path: Path
) -> None:
    path = imagegen.generate("a phoenix", tmp_path / "out" / "hero.png")

    assert path == tmp_path / "out" / "hero.jpg"
    assert path.read_bytes() == JPEG
    assert provider.bodies[-1] == {"model": "b64-model", "prompt": "a phoenix", "n": 1}
    # The user confirms generated images; the command must not pre-approve reading them.
    assert not (tmp_path / "tmp" / "agent-read-approved").exists()
    with pytest.raises(RuntimeError, match="already exists"):
        imagegen.generate("a phoenix", tmp_path / "out" / "hero.png")
    assert imagegen.generate("again", tmp_path / "out" / "hero.png", overwrite=True) == path


def test_url_image_is_downloaded_without_the_key(provider: _Provider, tmp_path: Path) -> None:
    path = imagegen.generate("x", tmp_path / "b.webp", model="url-model", size="1024x1024")

    assert path == tmp_path / "b.png"
    assert path.read_bytes() == PNG
    assert provider.bodies[-1]["size"] == "1024x1024"
    assert provider.download_auth is None


def test_missing_configuration_names_what_to_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATCHBAY_HOME", str(tmp_path))
    for var in ("IMAGEGEN_BASE_URL", "IMAGEGEN_MODEL"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(RuntimeError, match="IMAGEGEN_BASE_URL"):
        imagegen.generate("x", tmp_path / "a.png")
    monkeypatch.setenv("IMAGEGEN_BASE_URL", "http://127.0.0.1:9/v1")
    with pytest.raises(RuntimeError, match="IMAGEGEN_MODEL"):
        imagegen.generate("x", tmp_path / "a.png")
    monkeypatch.setenv("IMAGEGEN_MODEL", "m")
    with pytest.raises(RuntimeError, match="/settings"):
        imagegen.generate("x", tmp_path / "a.png")


@pytest.mark.usefixtures("provider")
async def test_key_check(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (await imagegen.verify_api_key(KEY)).detail == "2"
    assert (await imagegen.verify_api_key("sk-bad")).reason == "settings.err_imagegen_rejected"
    monkeypatch.delenv("IMAGEGEN_BASE_URL")
    assert (await imagegen.verify_api_key(KEY)).reason == "settings.err_imagegen_no_url"
