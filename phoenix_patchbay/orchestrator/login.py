"""``/login <provider> [account]``: sign a provider's CLI in from the chat.

A login is a short dialogue, not a single command: the bot sends a link, the
user signs in elsewhere, and the next plain message in the same chat or topic is
the code that finishes it. Providers register here by name so a second one
(anything else that has an interactive sign-in) is one entry in ``PROVIDERS``.
Providers that only need a key, like 9router, are configured in /settings and
have no login.

A provider can have several accounts to sign in (Claude: the default store plus
each entry of ``claude_accounts``). ``targets`` names them; the user picks one
with ``/login claude <account>``, and is asked to when there is more than one.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from phoenix_patchbay.cli.claude_accounts import (
    account_names,
    read_token,
    resolve_account_dir,
    save_token,
)
from phoenix_patchbay.i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable

    from phoenix_patchbay.orchestrator.core import Orchestrator
    from phoenix_patchbay.session.key import SessionKey

logger = logging.getLogger(__name__)

#: How long a started login waits for its code.
PENDING_TTL = 600.0

#: The command argument for a provider's default account. Named accounts use
#: their configured name; this is not one of those, so it cannot collide in
#: practice, and it does not change with the interface language.
DEFAULT_TARGET = "default"


class LoginFailedError(Exception):
    """The login could not continue. The message is safe to show the user."""


@dataclass(frozen=True, slots=True)
class Target:
    """One account a provider can sign in."""

    id: str
    label: str
    active: bool = False
    signed_in: bool = False


class LoginFlow(Protocol):
    """One provider account's sign-in dialogue."""

    async def start(self) -> str:
        """Begin; return what to tell the user (a link and what to do next)."""

    async def submit(self, text: str) -> str:
        """Finish with the user's reply; return what to tell the user."""

    def cancel(self) -> None:
        """Abandon the dialogue and free whatever it holds."""


@dataclass(frozen=True, slots=True)
class LoginProvider:
    """What /login needs to know about one provider."""

    label_key: str
    targets: Callable[[Orchestrator], list[Target]]
    flow: Callable[[Orchestrator, Target], LoginFlow]


def _claude_account_dir(orch: Orchestrator, target_id: str) -> str:
    """Credential-store directory for a Claude target ("" is the default store)."""
    if target_id == DEFAULT_TARGET:
        return ""
    return resolve_account_dir(orch._config.claude_accounts, target_id) or ""


def claude_targets(orch: Orchestrator) -> list[Target]:
    """The default account, then each configured one, marking the one in use."""
    config = orch._config
    active = config.claude_account or DEFAULT_TARGET
    ids = [DEFAULT_TARGET, *account_names(config.claude_accounts)]
    return [
        Target(
            id=i,
            label=t("account.default_label") if i == DEFAULT_TARGET else i,
            active=i == active,
            signed_in=bool(read_token(_claude_account_dir(orch, i))),
        )
        for i in ids
    ]


class ClaudeFlow:
    """Claude: ``claude setup-token``, kept as the token that account's runs use."""

    def __init__(self, orch: Orchestrator, target: Target) -> None:
        self._target = target
        self._account_dir = _claude_account_dir(orch, target.id)
        self._login: object | None = None

    def _new(self) -> object:
        try:
            from phoenix_patchbay.cli.claude_login import ClaudeLogin
        except ImportError as exc:  # no pty module: Windows
            raise LoginFailedError(t("login.unsupported")) from exc
        return ClaudeLogin()

    async def start(self) -> str:
        from phoenix_patchbay.cli.claude_login import LoginError

        self._login = self._new()
        try:
            url = await self._login.start()  # type: ignore[attr-defined]
        except LoginError as exc:
            raise LoginFailedError(str(exc)) from exc
        return t("login.claude.started", url=url, account=self._target.label)

    async def submit(self, text: str) -> str:
        from phoenix_patchbay.cli.claude_login import LoginError

        try:
            token = await self._login.finish(text)  # type: ignore[union-attr]
        except LoginError as exc:
            raise LoginFailedError(str(exc)) from exc
        save_token(self._account_dir, token)
        logger.info("Claude login saved for account %r", self._target.id)
        return t("login.claude.saved", account=self._target.label, id=self._target.id)

    def cancel(self) -> None:
        if self._login is not None:
            self._login.cancel()  # type: ignore[attr-defined]


PROVIDERS: dict[str, LoginProvider] = {
    "claude": LoginProvider("login.claude.label", claude_targets, ClaudeFlow),
}


class LoginFlows:
    """The logins waiting for a code, one per chat or topic."""

    def __init__(self) -> None:
        self._pending: dict[SessionKey, tuple[LoginFlow, float]] = {}

    def _live(self, key: SessionKey) -> LoginFlow | None:
        entry = self._pending.get(key)
        if entry is None:
            return None
        flow, started = entry
        if time.monotonic() - started > PENDING_TTL:
            flow.cancel()
            del self._pending[key]
            return None
        return flow

    async def begin(
        self, key: SessionKey, provider: str, target: Target, orch: Orchestrator
    ) -> str:
        """Start *provider*'s login for *target* here, replacing one already waiting."""
        self.cancel(key)
        flow = PROVIDERS[provider].flow(orch, target)
        try:
            text = await flow.start()
        except LoginFailedError as exc:
            flow.cancel()
            return t("login.failed", reason=str(exc))
        self._pending[key] = (flow, time.monotonic())
        return text

    async def submit(self, key: SessionKey, text: str) -> str | None:
        """Treat *text* as the code for a login waiting here; None if none is."""
        flow = self._live(key)
        if flow is None:
            return None
        try:
            return await flow.submit(text)
        except LoginFailedError as exc:
            return t("login.failed", reason=str(exc))
        finally:
            # A wrong code ends the dialogue: the CLI has consumed its state.
            self._pending.pop(key, None)
            flow.cancel()

    def cancel(self, key: SessionKey) -> bool:
        entry = self._pending.pop(key, None)
        if entry is None:
            return False
        entry[0].cancel()
        return True


def login_list() -> str:
    """The provider list /login shows."""
    lines = [
        f"/login {name} — {t(provider.label_key)}" for name, provider in sorted(PROVIDERS.items())
    ]
    return t("login.list", providers="\n".join(lines))


def target_list(provider: str, orch: Orchestrator) -> str:
    """The accounts of *provider* to choose from, marking the one in use."""
    lines = []
    for target in PROVIDERS[provider].targets(orch):
        marks = [
            m
            for m, on in (
                (t("login.in_use"), target.active),
                (t("login.signed_in"), target.signed_in),
            )
            if on
        ]
        suffix = f" ({', '.join(marks)})" if marks else ""
        lines.append(f"/login {provider} {target.id}{suffix}")
    return t("login.choose", provider=provider, accounts="\n".join(lines))
