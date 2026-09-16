"""Asking Google whether a key works, and saying so in terms a person can act on.

The question asked is the point of these tests. Listing models proves a key can
read metadata; it says nothing about generating, and on 2026-09-15 a denied
account answered 200 to the list and 403 to every generate call. `/settings`
showed a green tick, no handoff could be written, and three keys were made
chasing a fault that was never in the key.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from phoenix_patchbay.cli.gemini_verify import verify_gemini_key

KEY = "AIzaSyDUMMYdummyDUMMYdummyDUMMYdummy1234"

DENIED = {
    "error": {
        "code": 403,
        "message": "Your project has been denied access. Please contact support.",
        "status": "PERMISSION_DENIED",
    }
}


def _session_returning(status: int, body: Any = None) -> MagicMock:
    """A ClientSession whose POST yields one canned response."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=body if body is not None else {})

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.post = MagicMock(return_value=ctx)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.mark.asyncio
async def test_a_working_key_is_accepted() -> None:
    session = _session_returning(200, {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is True


@pytest.mark.asyncio
async def test_it_asks_the_model_to_generate_not_to_list() -> None:
    """The whole point: prove the key can do the job it is stored for."""
    session = _session_returning(200, {"candidates": []})
    with patch("aiohttp.ClientSession", return_value=session):
        await verify_gemini_key(KEY)

    url = session.post.call_args.args[0]
    assert url.endswith(":generateContent")
    assert "gemini-3.5-flash-lite" in url, "verify the model the write-up actually uses"
    # One token: enough to exercise generation, cheap enough to run on every paste.
    assert session.post.call_args.kwargs["json"]["generationConfig"]["maxOutputTokens"] == 1


@pytest.mark.asyncio
async def test_a_key_that_can_only_list_models_is_not_accepted() -> None:
    """The exact production failure: 200 on ListModels, 403 on every generate."""
    session = _session_returning(403, DENIED)
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is False, "a green tick here means no handoff can ever be written"


@pytest.mark.asyncio
async def test_googles_own_words_reach_the_user() -> None:
    """ "Denied access" is a different errand from "you mistyped it"."""
    session = _session_returning(403, DENIED)
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.reason == "settings.err_refused_detail"
    assert "denied access" in result.detail
    assert "\n" not in result.detail


@pytest.mark.asyncio
async def test_the_key_travels_in_a_header_not_the_url() -> None:
    """A URL ends up in logs, proxies and error messages. This one is a secret."""
    session = _session_returning(200, {"candidates": []})
    with patch("aiohttp.ClientSession", return_value=session):
        await verify_gemini_key(KEY)

    url = session.post.call_args.args[0]
    assert KEY not in url
    assert session.post.call_args.kwargs["headers"]["x-goog-api-key"] == KEY


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 400, 404])
async def test_a_key_google_refuses_is_reported_as_refused(status: int) -> None:
    session = _session_returning(status)
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_rejected"


@pytest.mark.asyncio
async def test_an_exhausted_quota_is_not_a_bad_key() -> None:
    """Saying "invalid key" here sends someone to make a second one for nothing."""
    session = _session_returning(429, {"error": {"message": "Quota exceeded"}})
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_quota"


@pytest.mark.asyncio
async def test_googles_own_outage_is_not_blamed_on_the_key() -> None:
    session = _session_returning(503)
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_upstream"


@pytest.mark.asyncio
async def test_a_timeout_is_not_an_endorsement() -> None:
    """Unreachable must never store the key: ok=False is the safe answer."""
    with patch("aiohttp.ClientSession", side_effect=TimeoutError):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_timeout"


@pytest.mark.asyncio
async def test_no_network_is_reported_as_no_network() -> None:
    with patch("aiohttp.ClientSession", side_effect=aiohttp.ClientError("dns")):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_network"


@pytest.mark.asyncio
async def test_an_unexpected_bug_does_not_become_your_key_is_bad() -> None:
    with patch("aiohttp.ClientSession", side_effect=RuntimeError("boom")):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_network"


@pytest.mark.asyncio
async def test_an_empty_value_never_reaches_the_network() -> None:
    with patch("aiohttp.ClientSession") as session:
        result = await verify_gemini_key("   ")

    assert result.ok is False
    assert result.reason == "settings.err_empty"
    session.assert_not_called()


@pytest.mark.asyncio
async def test_a_malformed_failure_body_still_refuses() -> None:
    """No explanation to quote is no reason to accept the key."""
    session = _session_returning(403, {"unexpected": True})
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_rejected"
    assert result.detail == ""
