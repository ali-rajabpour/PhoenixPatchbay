"""Claude credential-store account switching.

Claude Code reads its OAuth credentials from the directory named by
``CLAUDE_SECURESTORAGE_CONFIG_DIR`` (falling back to the regular config dir).
Only the *credential store* moves — ``CLAUDE_CONFIG_DIR`` is left alone, so
sessions, projects, skills, MCP servers and settings stay shared.

That split is what makes account switching useful mid-conversation: when one
subscription hits its rate limit, pointing the credential store at a second
account lets ``claude --resume`` continue the *same* session on the other
subscription, exactly like running a wrapper script that exports the variable.

Platform note: on macOS the directory is hashed into the Keychain service name;
on Linux it holds a ``.credentials.json`` file. Both honour the variable, so the
same config works on either host.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping
from pathlib import Path

#: Environment variable Claude Code reads the credential-store path from.
ENV_VAR = "CLAUDE_SECURESTORAGE_CONFIG_DIR"

#: Environment variable Claude Code reads a long-lived OAuth token from. It
#: takes precedence over the credential file, so the CLI never refreshes or
#: rewrites that file, which is what lets every unix account share one login.
TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105 - a variable name, not a secret
#: Where /login keeps the token, inside the account's credential-store directory.
TOKEN_FILE = ".patchbay_oauth_token"  # noqa: S105 - a file name, not a secret


def resolve_account_dir(accounts: Mapping[str, str], active: str) -> str | None:
    """Return the credential-store directory for the *active* account.

    Returns ``None`` when the default store should be used — either because no
    account is selected, the name is unknown, or its configured path is empty.
    ``None`` means "leave ``CLAUDE_SECURESTORAGE_CONFIG_DIR`` unset", which is
    not the same as setting it to an empty string (Claude Code treats an empty
    value as ``~/.claude``, ignoring a custom ``CLAUDE_CONFIG_DIR``).
    """
    if not active:
        return None
    raw = accounts.get(active, "").strip()
    if not raw:
        return None
    return str(Path(raw).expanduser())


def apply_to_env(env: dict[str, str], account_dir: str | None) -> dict[str, str]:
    """Set or clear ``CLAUDE_SECURESTORAGE_CONFIG_DIR`` in *env*, in place.

    Clearing means removing the key entirely. Setting it to an empty string is
    not equivalent: Claude Code reads an empty value as ``~/.claude``, which
    would silently ignore a custom ``CLAUDE_CONFIG_DIR``.
    """
    if account_dir:
        env[ENV_VAR] = account_dir
    else:
        env.pop(ENV_VAR, None)
    return env


def usable_accounts(accounts: Mapping[str, str]) -> dict[str, str]:
    """Drop entries whose path is blank.

    A name mapped to an empty or whitespace path passes a naive membership check
    but resolves to the default store, so the UI would report an account that is
    not the one being used. Such entries are treated as not configured.
    """
    return {name: path for name, path in accounts.items() if path and path.strip()}


def account_names(accounts: Mapping[str, str]) -> list[str]:
    """Return usable account names in a stable, display-friendly order."""
    return sorted(usable_accounts(accounts))


def is_known_account(accounts: Mapping[str, str], name: str) -> bool:
    """Return ``True`` for the default account ("") or a usable configured name."""
    return not name or name in usable_accounts(accounts)


def active_claude_account_dir(config: object) -> str:
    """Resolved credential store for *config*'s selected account, or "".

    Shared by every auth probe so status, startup and the welcome screen all
    describe the account the agent will actually run as.
    """
    from phoenix_patchbay.cli.claude_accounts import resolve_account_dir

    return (
        resolve_account_dir(
            getattr(config, "claude_accounts", {}) or {},
            getattr(config, "claude_account", "") or "",
        )
        or ""
    )


def token_path(account_dir: str | None) -> Path:
    """Where the /login token for *account_dir* lives (default store when empty)."""
    if account_dir:
        return Path(account_dir).expanduser() / TOKEN_FILE
    base = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return (Path(base).expanduser() if base else Path.home() / ".claude") / TOKEN_FILE


def read_token(account_dir: str | None) -> str:
    """The saved /login token, or "" when there is none."""
    try:
        return token_path(account_dir).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_token(account_dir: str | None, token: str) -> Path:
    """Write the token owner-only, replacing any earlier one."""
    path = token_path(account_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token + "\n")
    tmp.replace(path)
    return path


def forget_token(account_dir: str | None) -> None:
    """Remove the saved token, if any."""
    with contextlib.suppress(OSError):
        token_path(account_dir).unlink()


def apply_token_to_env(env: dict[str, str], account_dir: str | None) -> dict[str, str]:
    """Pass the /login token to the CLI, when one was saved.

    Leaves *env* alone otherwise, so a token exported by hand, or a credential
    file from an ordinary ``claude`` login, keeps working.
    """
    if token := read_token(account_dir):
        env[TOKEN_ENV] = token
    return env
