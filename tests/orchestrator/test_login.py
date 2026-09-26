"""/login: providers and accounts are looked up by name, and a waiting login takes the next reply."""

from __future__ import annotations

import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from phoenix_patchbay.cli import claude_login
from phoenix_patchbay.cli.claude_accounts import read_token
from phoenix_patchbay.orchestrator import login
from phoenix_patchbay.orchestrator.commands import cmd_login
from phoenix_patchbay.orchestrator.login import LoginFailedError, LoginFlows, Target
from phoenix_patchbay.session.key import SessionKey

KEY = SessionKey.telegram(1, 7)
TOKEN = "sk-ant-oat01-" + "x" * 40


class FakeFlow:
    def __init__(self, _orch: object, _target: Target) -> None:
        self.cancelled = False

    async def start(self) -> str:
        return "open the link"

    async def submit(self, text: str) -> str:
        if text != "good":
            msg = "nope"
            raise LoginFailedError(msg)
        return "logged in"

    def cancel(self) -> None:
        self.cancelled = True


class FakeClaudeLogin:
    """Stands in for the pty dialogue with the real CLI."""

    async def start(self) -> str:
        return "https://claude.com/cai/oauth/authorize?x"

    async def finish(self, _code: str) -> str:
        return TOKEN

    def cancel(self) -> None:
        pass


def _orch(accounts: dict[str, str] | None = None, active: str = "") -> Any:
    return SimpleNamespace(
        _config=SimpleNamespace(claude_accounts=accounts or {}, claude_account=active),
        _logins=LoginFlows(),
    )


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = login.LoginProvider("login.claude.label", lambda _o: [Target("x", "x")], FakeFlow)
    monkeypatch.setitem(login.PROVIDERS, "fake", fake)


@pytest.mark.usefixtures("fake_provider")
async def test_next_reply_is_the_code() -> None:
    flows, target = LoginFlows(), Target("x", "x")
    assert await flows.submit(KEY, "good") is None  # nothing waiting: goes to the agent
    assert await flows.begin(KEY, "fake", target, object()) == "open the link"  # type: ignore[arg-type]
    assert await flows.submit(SessionKey.telegram(1, 8), "good") is None  # another topic
    assert await flows.submit(KEY, "good") == "logged in"
    assert await flows.submit(KEY, "good") is None  # one code, one login


@pytest.mark.usefixtures("fake_provider")
async def test_wrong_code_ends_the_login() -> None:
    flows, target = LoginFlows(), Target("x", "x")
    await flows.begin(KEY, "fake", target, object())  # type: ignore[arg-type]
    reply = await flows.submit(KEY, "bad")
    assert reply is not None
    assert "nope" in reply
    assert await flows.submit(KEY, "good") is None


@pytest.mark.usefixtures("fake_provider")
async def test_cancel_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    flows, target = LoginFlows(), Target("x", "x")
    await flows.begin(KEY, "fake", target, object())  # type: ignore[arg-type]
    assert flows.cancel(KEY) is True
    assert flows.cancel(KEY) is False

    await flows.begin(KEY, "fake", target, object())  # type: ignore[arg-type]
    monkeypatch.setattr(login, "PENDING_TTL", -1.0)
    assert await flows.submit(KEY, "good") is None


def test_list_names_the_provider() -> None:
    text = login.login_list()
    assert "/login claude" in text
    assert "9router" in text


async def test_one_account_needs_no_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(claude_login, "ClaudeLogin", FakeClaudeLogin)
    reply = await cmd_login(_orch(), KEY, "/login claude")
    assert "authorize" in reply.text


async def test_two_accounts_must_be_told_apart(tmp_path: Path) -> None:
    orch = _orch({"claude2": str(tmp_path / "second")}, active="claude2")
    reply = await cmd_login(orch, KEY, "/login claude")
    # Never guesses: it lists both, marks the one in use, and starts nothing.
    assert "/login claude default" in reply.text
    assert "/login claude claude2 (in use)" in reply.text
    assert await orch._logins.submit(KEY, "code") is None

    reply = await cmd_login(orch, KEY, "/login claude nosuch")
    assert "nosuch" in reply.text
    assert "/login claude claude2" in reply.text


async def test_each_account_keeps_its_own_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    default_dir, second = tmp_path / "default", tmp_path / "second"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(default_dir))
    monkeypatch.setattr(claude_login, "ClaudeLogin", FakeClaudeLogin)
    orch = _orch({"claude2": str(second)})

    await cmd_login(orch, KEY, "/login claude claude2")
    reply = await orch._logins.submit(KEY, "code")
    assert reply is not None
    assert "claude2" in reply
    assert read_token(str(second)) == TOKEN
    assert read_token("") == ""  # the default account was not touched
    assert stat.S_IMODE((second / ".patchbay_oauth_token").stat().st_mode) == 0o600

    await cmd_login(orch, KEY, "/login claude default")
    await orch._logins.submit(KEY, "code")
    assert read_token("") == TOKEN
    assert (default_dir / ".patchbay_oauth_token").exists()

    # The list now shows both as signed in.
    listing = await cmd_login(orch, KEY, "/login claude")
    assert listing.text.count("token saved") == 2
