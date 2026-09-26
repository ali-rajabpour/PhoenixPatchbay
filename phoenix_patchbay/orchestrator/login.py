"""``/login <provider>``: sign a provider's CLI in from the chat.

A login is a short dialogue, not a single command: the bot sends a link, the
user signs in elsewhere, and the next plain message in the same chat or topic is
the code that finishes it. Providers register here by name so a second one
(anything else that has an interactive sign-in) is one entry in ``PROVIDERS``.
Providers that only need a key, like 9router, are configured in /settings and
have no login.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Protocol

from phoenix_patchbay.cli.claude_accounts import save_token
from phoenix_patchbay.i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable

    from phoenix_patchbay.orchestrator.core import Orchestrator
    from phoenix_patchbay.session.key import SessionKey

logger = logging.getLogger(__name__)

#: How long a started login waits for its code.
PENDING_TTL = 600.0


class LoginFailedError(Exception):
    """The login could not continue. The message is safe to show the user."""


class LoginFlow(Protocol):
    """One provider's sign-in dialogue."""

    async def start(self) -> str:
        """Begin; return what to tell the user (a link and what to do next)."""

    async def submit(self, text: str) -> str:
        """Finish with the user's reply; return what to tell the user."""

    def cancel(self) -> None:
        """Abandon the dialogue and free whatever it holds."""


class ClaudeFlow:
    """Claude: ``claude setup-token``, stored as the token every Claude run uses."""

    def __init__(self, orch: Orchestrator) -> None:
        from phoenix_patchbay.cli.claude_accounts import active_claude_account_dir

        self._account_dir = active_claude_account_dir(orch._config)
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
        return t("login.claude.started", url=url)

    async def submit(self, text: str) -> str:
        from phoenix_patchbay.cli.claude_login import LoginError

        try:
            token = await self._login.finish(text)  # type: ignore[union-attr]
        except LoginError as exc:
            raise LoginFailedError(str(exc)) from exc
        save_token(self._account_dir, token)
        logger.info("Claude login saved")
        return t("login.claude.saved")

    def cancel(self) -> None:
        if self._login is not None:
            self._login.cancel()  # type: ignore[attr-defined]


#: name -> (translation key of the label shown in /login, flow factory)
PROVIDERS: dict[str, tuple[str, Callable[[Orchestrator], LoginFlow]]] = {
    "claude": ("login.claude.label", ClaudeFlow),
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

    async def begin(self, key: SessionKey, provider: str, orch: Orchestrator) -> str:
        """Start *provider*'s login here, replacing one already waiting."""
        self.cancel(key)
        flow = PROVIDERS[provider][1](orch)
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
    lines = [f"/login {name} — {t(label_key)}" for name, (label_key, _) in sorted(PROVIDERS.items())]
    return t("login.list", providers="\n".join(lines))
