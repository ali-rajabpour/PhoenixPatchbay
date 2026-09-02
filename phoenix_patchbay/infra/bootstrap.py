"""Write a usable config from environment variables on first start.

Without this, a container's first run reaches the interactive setup wizard,
which needs a TTY it does not have, prints its banner and exits — so the
container restart-loops and the logs look like a crash rather than a missing
answer. Someone deploying with `docker compose up` has already supplied the
only two facts the wizard would ask for; this reads them from the environment
instead of from a keyboard.

Existing config is never touched. The bootstrap is for the empty case only.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TOKEN_VAR = "TELEGRAM_BOT_TOKEN"  # noqa: S105 - the name of a variable, not a secret
USERS_VAR = "TELEGRAM_ALLOWED_USER_IDS"
ROOTS_VAR = "PATCHBAY_PROJECT_ROOTS"


def _user_ids(raw: str) -> list[int]:
    """Parse `123,456` into ids, ignoring anything that is not a number.

    A malformed entry must not become an empty allowlist: an allowlist that
    silently empties is a bot that answers strangers.
    """
    ids = []
    for raw_part in raw.replace(";", ",").split(","):
        part = raw_part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
        elif part:
            logger.warning("Ignoring non-numeric user id %r in %s", part, USERS_VAR)
    return ids


def _project_roots(raw: str) -> dict[str, str]:
    """Parse `label=/path,label2=/path2`, or bare paths named after their folder."""
    roots: dict[str, str] = {}
    for raw_part in raw.split(","):
        part = raw_part.strip()
        if not part:
            continue
        label, _, path = part.partition("=")
        if path:
            roots[label.strip()] = path.strip()
        else:
            roots[Path(part).name] = part
    return roots


def config_from_env() -> dict[str, Any] | None:
    """The config a fresh deployment implies, or None when the token is absent."""
    token = os.environ.get(TOKEN_VAR, "").strip()
    if not token:
        return None

    config: dict[str, Any] = {
        "telegram_bot_token": token,
        "allowed_user_ids": _user_ids(os.environ.get(USERS_VAR, "")),
    }
    roots = os.environ.get(ROOTS_VAR, "").strip()
    if roots:
        config["project_roots"] = _project_roots(roots)
    return config


def ensure_config(config_path: Path) -> bool:
    """Create *config_path* from the environment. True when it wrote one.

    Returns False when a config already exists or no token was supplied —
    both are ordinary, and neither is an error worth failing a start over.
    """
    if config_path.exists():
        return False

    config = config_from_env()
    if config is None:
        return False

    if not config["allowed_user_ids"]:
        # A bot with an empty allowlist answers anyone who finds it. Refuse to
        # write that config rather than start something the operator did not ask
        # for; the wizard would have insisted on the same answer.
        logger.error(
            "%s is set but %s is empty — refusing to start a bot anyone can talk to",
            TOKEN_VAR,
            USERS_VAR,
        )
        raise SystemExit(1)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    config_path.chmod(0o600)  # it holds a bot token
    logger.info("Wrote %s from environment (%d allowed user(s))", config_path, len(config["allowed_user_ids"]))
    return True
