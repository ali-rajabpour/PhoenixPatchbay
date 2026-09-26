"""/login: providers are looked up by name, and a waiting login takes the next reply."""

from __future__ import annotations

import pytest

from phoenix_patchbay.orchestrator import login
from phoenix_patchbay.orchestrator.login import LoginFailedError, LoginFlows
from phoenix_patchbay.session.key import SessionKey

KEY = SessionKey.telegram(1, 7)


class FakeFlow:
    def __init__(self, _orch: object) -> None:
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


@pytest.fixture(autouse=True)
def _fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(login.PROVIDERS, "fake", ("login.claude.label", FakeFlow))


async def test_next_reply_is_the_code() -> None:
    flows = LoginFlows()
    assert await flows.submit(KEY, "good") is None  # nothing waiting: goes to the agent
    assert await flows.begin(KEY, "fake", object()) == "open the link"  # type: ignore[arg-type]
    assert await flows.submit(SessionKey.telegram(1, 8), "good") is None  # another topic
    assert await flows.submit(KEY, "good") == "logged in"
    assert await flows.submit(KEY, "good") is None  # one code, one login


async def test_wrong_code_ends_the_login() -> None:
    flows = LoginFlows()
    await flows.begin(KEY, "fake", object())  # type: ignore[arg-type]
    reply = await flows.submit(KEY, "bad")
    assert reply is not None
    assert "nope" in reply
    assert await flows.submit(KEY, "good") is None


async def test_cancel_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    flows = LoginFlows()
    await flows.begin(KEY, "fake", object())  # type: ignore[arg-type]
    assert flows.cancel(KEY) is True
    assert flows.cancel(KEY) is False

    await flows.begin(KEY, "fake", object())  # type: ignore[arg-type]
    monkeypatch.setattr(login, "PENDING_TTL", -1.0)
    assert await flows.submit(KEY, "good") is None


def test_list_names_the_provider() -> None:
    text = login.login_list()
    assert "/login claude" in text
    assert "9router" in text
