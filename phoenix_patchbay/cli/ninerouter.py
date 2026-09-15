"""9router backend: the Claude Code CLI pointed at a 9router endpoint.

9router (https://github.com/decolua/9router) speaks the Anthropic Messages API,
so no separate CLI is needed. A 9router model is addressed as
``9router/<router-model>`` (``9router/cc/claude-sonnet-4-5``, or a combo name);
the prefix picks the provider and is stripped before the model reaches the CLI.

The address and model list come from the environment, or ``~/.phoenix-patchbay/.env``:

- ``NINEROUTER_BASE_URL``  e.g. ``http://localhost:20128`` (a trailing ``/v1`` is fine)
- ``NINEROUTER_MODELS``    optional comma list; otherwise ``GET /v1/models`` is asked

The key is set only from ``/settings`` (``ninerouter_api_key`` in ``config.json``).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

import aiohttp

from phoenix_patchbay.cli.gemini_verify import VerifyResult

logger = logging.getLogger(__name__)

PROVIDER = "9router"
MODEL_PREFIX = "9router/"
_ENV_KEYS = ("NINEROUTER_BASE_URL", "NINEROUTER_MODELS")


def settings(env: dict[str, str] | None = None) -> dict[str, str]:
    """Address and models from process env, then the patchbay ``.env``; key from /settings."""
    source = os.environ if env is None else env
    values = {k: source.get(k, "").strip() for k in _ENV_KEYS}
    if env is None and not all(values.values()):
        from phoenix_patchbay.infra.env_secrets import load_env_secrets
        from phoenix_patchbay.workspace.paths import resolve_paths

        secrets = load_env_secrets(resolve_paths().env_file)
        for k in _ENV_KEYS:
            values[k] = values[k] or secrets.get(k, "").strip()
    values["NINEROUTER_API_KEY"] = _stored_api_key() if env is None else ""
    values["NINEROUTER_BASE_URL"] = values["NINEROUTER_BASE_URL"].rstrip("/").removesuffix("/v1")
    return values


def _stored_api_key() -> str:
    """The key saved from ``/settings``. Read from disk so a new key applies at once."""
    from phoenix_patchbay.workspace.paths import resolve_paths

    try:
        data = json.loads(resolve_paths().config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    raw = data.get("ninerouter_api_key") if isinstance(data, dict) else None
    key = raw.strip() if isinstance(raw, str) else ""
    return "" if key.lower() in ("", "null", "none", "-") else key


def is_configured() -> bool:
    return bool(settings()["NINEROUTER_BASE_URL"])


def list_models(timeout: float = 5.0) -> tuple[list[str], list[str]]:
    """Return ``(combos, single models)`` as ``9router/``-prefixed IDs.

    From NINEROUTER_MODELS or the live endpoint. The router marks combos with
    ``owned_by: "combo"``; a name from NINEROUTER_MODELS is a combo when it has
    no ``provider/`` prefix, which is how 9router names them.
    """
    cfg = settings()
    names = [m.strip() for m in cfg["NINEROUTER_MODELS"].split(",") if m.strip()]
    combo_ids = {n for n in names if "/" not in n}
    if not names and cfg["NINEROUTER_BASE_URL"]:
        req = urllib.request.Request(f"{cfg['NINEROUTER_BASE_URL']}/v1/models")  # noqa: S310
        if cfg["NINEROUTER_API_KEY"]:
            req.add_header("Authorization", f"Bearer {cfg['NINEROUTER_API_KEY']}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                data = [m for m in json.load(resp).get("data", []) if m.get("id")]
            names = [m["id"] for m in data]
            combo_ids = {m["id"] for m in data if m.get("owned_by") == "combo"}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("9router model list failed: %s", exc)
    combos = [f"{MODEL_PREFIX}{n}" for n in names if n in combo_ids]
    singles = [f"{MODEL_PREFIX}{n}" for n in names if n not in combo_ids]
    return combos, singles


def apply_to_env(env: dict[str, str]) -> None:
    """Point the Claude CLI subprocess at 9router instead of Anthropic."""
    cfg = settings()
    env["ANTHROPIC_BASE_URL"] = cfg["NINEROUTER_BASE_URL"]
    # An inherited real Anthropic key would win over the auth token.
    env.pop("ANTHROPIC_API_KEY", None)
    if cfg["NINEROUTER_API_KEY"]:
        env["ANTHROPIC_AUTH_TOKEN"] = cfg["NINEROUTER_API_KEY"]


async def verify_api_key(key: str) -> VerifyResult:
    """Ask the configured 9router whether *key* works: one ``GET /v1/models``. Never raises."""
    candidate = key.strip()
    if not candidate:
        return VerifyResult(ok=False, reason="settings.err_empty")
    base_url = settings()["NINEROUTER_BASE_URL"]
    if not base_url:
        return VerifyResult(ok=False, reason="settings.err_ninerouter_no_url")
    try:
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
            session.get(
                f"{base_url}/v1/models", headers={"Authorization": f"Bearer {candidate}"}
            ) as response,
        ):
            if response.status in (401, 403):
                return VerifyResult(ok=False, reason="settings.err_ninerouter_rejected")
            if response.status != 200:
                return VerifyResult(ok=False, reason="settings.err_ninerouter_unreachable")
            body = await response.json(content_type=None)
    except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
        logger.warning("9router key check failed: %s", exc)
        return VerifyResult(ok=False, reason="settings.err_ninerouter_unreachable")
    count = len(body.get("data") or []) if isinstance(body, dict) else 0
    return VerifyResult(ok=True, reason="settings.verified_ninerouter", detail=str(count))
