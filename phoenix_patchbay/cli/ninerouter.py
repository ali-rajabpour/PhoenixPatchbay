"""9router backend: the Claude Code CLI pointed at a 9router endpoint.

9router (https://github.com/decolua/9router) speaks the Anthropic Messages API,
so no separate CLI is needed. A 9router model is addressed as
``9router/<router-model>`` (``9router/cc/claude-sonnet-4-5``, or a combo name);
the prefix picks the provider and is stripped before the model reaches the CLI.

Configured entirely from the environment, or ``~/.phoenix-patchbay/.env``:

- ``NINEROUTER_BASE_URL``  e.g. ``http://localhost:20128`` (a trailing ``/v1`` is fine)
- ``NINEROUTER_API_KEY``   the key from the 9router dashboard
- ``NINEROUTER_MODELS``    optional comma list; otherwise ``GET /v1/models`` is asked
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

PROVIDER = "9router"
MODEL_PREFIX = "9router/"
_KEYS = ("NINEROUTER_BASE_URL", "NINEROUTER_API_KEY", "NINEROUTER_MODELS")


def settings(env: dict[str, str] | None = None) -> dict[str, str]:
    """Return the NINEROUTER_* values, process env first, then the patchbay ``.env``."""
    source = os.environ if env is None else env
    values = {k: source.get(k, "").strip() for k in _KEYS}
    if env is None and not all(values.values()):
        from phoenix_patchbay.infra.env_secrets import load_env_secrets
        from phoenix_patchbay.workspace.paths import resolve_paths

        secrets = load_env_secrets(resolve_paths().env_file)
        for k in _KEYS:
            values[k] = values[k] or secrets.get(k, "").strip()
    values["NINEROUTER_BASE_URL"] = values["NINEROUTER_BASE_URL"].rstrip("/").removesuffix("/v1")
    return values


def is_configured() -> bool:
    return bool(settings()["NINEROUTER_BASE_URL"])


def list_models(timeout: float = 5.0) -> list[str]:
    """Return ``9router/``-prefixed model IDs, from NINEROUTER_MODELS or the live endpoint."""
    cfg = settings()
    names = [m.strip() for m in cfg["NINEROUTER_MODELS"].split(",") if m.strip()]
    if not names and cfg["NINEROUTER_BASE_URL"]:
        req = urllib.request.Request(f"{cfg['NINEROUTER_BASE_URL']}/v1/models")  # noqa: S310
        if cfg["NINEROUTER_API_KEY"]:
            req.add_header("Authorization", f"Bearer {cfg['NINEROUTER_API_KEY']}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                names = [m["id"] for m in json.load(resp).get("data", []) if m.get("id")]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("9router model list failed: %s", exc)
    return [f"{MODEL_PREFIX}{n}" for n in names]


def apply_to_env(env: dict[str, str]) -> None:
    """Point the Claude CLI subprocess at 9router instead of Anthropic."""
    cfg = settings(env) if env.get("NINEROUTER_BASE_URL") else settings()
    env["ANTHROPIC_BASE_URL"] = cfg["NINEROUTER_BASE_URL"]
    # An inherited real Anthropic key would win over the auth token.
    env.pop("ANTHROPIC_API_KEY", None)
    if cfg["NINEROUTER_API_KEY"]:
        env["ANTHROPIC_AUTH_TOKEN"] = cfg["NINEROUTER_API_KEY"]
