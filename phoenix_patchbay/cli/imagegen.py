"""Image generation through any OpenAI-compatible images API.

``patchbay image`` runs this for agents, whatever model they run on. The
endpoint and default model come from the environment, or
``~/.phoenix-patchbay/.env``:

- ``IMAGEGEN_BASE_URL``  OpenAI style, including ``/v1`` (``https://api.openai.com/v1``)
- ``IMAGEGEN_MODEL``     default model; ``--model`` overrides it per call

The key is set only from ``/settings`` (``imagegen_api_key`` in ``config.json``)
and read from disk on every call. It never has to be in an agent's environment,
and a key replaced in ``/settings`` applies to the next call.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

import aiohttp

from phoenix_patchbay.cli.gemini_verify import VerifyResult

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_ENV_KEYS = ("IMAGEGEN_BASE_URL", "IMAGEGEN_MODEL")
_TIMEOUT = 180
_MAGIC = {b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"RIFF": ".webp"}


def settings() -> dict[str, str]:
    """``IMAGEGEN_*`` from the process env first, then the patchbay ``.env``."""
    values = {k: os.environ.get(k, "").strip() for k in _ENV_KEYS}
    if not all(values.values()):
        from phoenix_patchbay.infra.env_secrets import load_env_secrets
        from phoenix_patchbay.workspace.paths import resolve_paths

        secrets = load_env_secrets(resolve_paths().env_file)
        for k in _ENV_KEYS:
            values[k] = values[k] or secrets.get(k, "").strip()
    values["IMAGEGEN_BASE_URL"] = values["IMAGEGEN_BASE_URL"].rstrip("/")
    return values


def _stored_api_key() -> str:
    """The key saved from ``/settings``, read from disk so a new key applies at once."""
    from phoenix_patchbay.workspace.paths import resolve_paths

    try:
        data = json.loads(resolve_paths().config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    raw = data.get("imagegen_api_key") if isinstance(data, dict) else None
    key = raw.strip() if isinstance(raw, str) else ""
    return "" if key.lower() in ("", "null", "none", "-") else key


async def verify_api_key(key: str) -> VerifyResult:
    """Ask the image provider whether *key* works: one ``GET /models``. Never raises.

    A provider that lists its models without authentication accepts any key
    here; the first real generation is what exposes a bad one.
    """
    candidate = key.strip()
    if not candidate:
        return VerifyResult(ok=False, reason="settings.err_empty")
    base_url = settings()["IMAGEGEN_BASE_URL"]
    if not base_url:
        return VerifyResult(ok=False, reason="settings.err_imagegen_no_url")
    try:
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
            session.get(
                f"{base_url}/models", headers={"Authorization": f"Bearer {candidate}"}
            ) as response,
        ):
            if response.status in (401, 403):
                return VerifyResult(ok=False, reason="settings.err_imagegen_rejected")
            if response.status != 200:
                return VerifyResult(ok=False, reason="settings.err_imagegen_unreachable")
            body = await response.json(content_type=None)
    except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
        logger.warning("Image key check failed: %s", exc)
        return VerifyResult(ok=False, reason="settings.err_imagegen_unreachable")
    count = len(body.get("data") or []) if isinstance(body, dict) else 0
    return VerifyResult(ok=True, reason="settings.verified_imagegen", detail=str(count))


def _read(request: urllib.request.Request) -> bytes:
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
            payload: bytes = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read(300).decode("utf-8", errors="replace")
        raise RuntimeError(f"image provider returned HTTP {exc.code}: {detail}") from None
    except OSError as exc:
        raise RuntimeError(f"image provider unreachable: {exc}") from None
    return payload


def _download(url: str) -> bytes:
    # No Authorization header: the image usually sits on a CDN that is not the
    # provider, and the key must not travel there.
    if not url.startswith(("https://", "http://")):
        raise RuntimeError("image provider returned a non-HTTP image URL")
    return _read(urllib.request.Request(url))  # noqa: S310


def generate(
    prompt: str, out: Path, *, model: str = "", size: str = "", overwrite: bool = False
) -> Path:
    """Generate one image, save it at *out*, and return the path actually written.

    The suffix follows the returned bytes, so a JPEG is never saved as ``.png``.
    ``size`` is sent only when given, leaving the default to the provider.
    Raises ``RuntimeError`` with a short message that never contains the key.
    """
    cfg = settings()
    model = model or cfg["IMAGEGEN_MODEL"]
    key = _stored_api_key()
    if not cfg["IMAGEGEN_BASE_URL"]:
        raise RuntimeError("IMAGEGEN_BASE_URL is not set (environment or ~/.phoenix-patchbay/.env)")
    if not model:
        raise RuntimeError("no model: pass --model or set IMAGEGEN_MODEL")
    if not key:
        raise RuntimeError("no image key: set it in /settings -> API keys -> Image generation")

    body: dict[str, Any] = {"model": model, "prompt": prompt, "n": 1}
    if size:
        body["size"] = size
    raw = _read(
        urllib.request.Request(  # noqa: S310
            f"{cfg['IMAGEGEN_BASE_URL']}/images/generations",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
    )
    try:
        item = json.loads(raw)["data"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        item = None
    fields: dict[str, Any] = item if isinstance(item, dict) else {}
    b64, url = fields.get("b64_json"), fields.get("url")
    if b64:
        try:
            image = base64.b64decode(str(b64))
        except ValueError:
            raise RuntimeError("image provider returned invalid base64") from None
    elif url:
        image = _download(str(url))
    else:
        raise RuntimeError(f"no image in response: {raw[:300].decode('utf-8', errors='replace')}")

    suffix = next((s for magic, s in _MAGIC.items() if image.startswith(magic)), out.suffix)
    path = out.with_suffix(suffix)
    if path.exists() and not overwrite:
        raise RuntimeError(f"{path} already exists; pass --overwrite or choose another name")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image)
    return path
