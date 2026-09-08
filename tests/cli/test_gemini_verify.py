"""Asking Google whether a key works, and saying so in terms a person can act on."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from phoenix_patchbay.cli.gemini_verify import verify_gemini_key

KEY = "AIzaSyDUMMYdummyDUMMYdummyDUMMYdummy1234"


def _session_returning(status: int, body: Any = None) -> MagicMock:
    """A ClientSession whose GET yields one canned response."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=body if body is not None else {})

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=ctx)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.mark.asyncio
async def test_a_working_key_is_accepted() -> None:
    session = _session_returning(200, {"models": [{"name": "a"}, {"name": "b"}]})
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is True
    # Evidence, not just a green tick.
    assert result.detail == "2"


@pytest.mark.asyncio
async def test_the_key_travels_in_a_header_not_the_url() -> None:
    """A URL ends up in logs, proxies and error messages. This one is a secret."""
    session = _session_returning(200, {"models": []})
    with patch("aiohttp.ClientSession", return_value=session):
        await verify_gemini_key(KEY)

    url = session.get.call_args.args[0]
    assert KEY not in url
    assert session.get.call_args.kwargs["headers"]["x-goog-api-key"] == KEY


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 400])
async def test_a_key_google_refuses_is_reported_as_refused(status: int) -> None:
    session = _session_returning(status)
    with patch("aiohttp.ClientSession", return_value=session):
        result = await verify_gemini_key(KEY)

    assert result.ok is False
    assert result.reason == "settings.err_rejected"


@pytest.mark.asyncio
async def test_an_exhausted_quota_is_not_a_bad_key() -> None:
    """Saying "invalid key" here sends someone to make a second one for nothing."""
    session = _session_returning(429)
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
async def test_a_malformed_success_body_still_counts_as_working() -> None:
    """200 is the answer; the model count is a nicety on top of it."""
    response_session = _session_returning(200, {"unexpected": True})
    with patch("aiohttp.ClientSession", return_value=response_session):
        result = await verify_gemini_key(KEY)

    assert result.ok is True
    assert result.detail == ""
