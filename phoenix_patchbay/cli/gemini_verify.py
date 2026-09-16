"""Ask Google whether a key can actually generate, not merely whether it reads.

A regex can only say "that looks like a key". It rejects a valid key whose
format changed, accepts a revoked one, and tells the user off for a typo it
cannot actually see. The API knows the answer, so ask it.

*Which* question is asked matters. This used to list models, because that is
the cheapest authenticated call there is. It is also the wrong one: on
2026-09-15 an account whose project had been denied access answered `200` to
`ListModels` and `403` to every `generateContent`, so `/settings` showed a
green tick while no handoff could be written. Three keys were generated chasing
a fault that was never in the key. So the check now asks for one token from the
model the write-up actually uses: the cheapest call that proves the thing the
key is stored for.

Failure is reported in the user's terms — wrong key, no quota, no network —
because "HTTP 400" is not something anyone can act on. When Google explains
itself, that sentence is passed through instead of being replaced by a guess:
"your project has been denied access" sends someone to support, while "check
you copied the whole thing" sends them to make a fourth key for nothing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)

#: The model the handoff writer is pinned to. Verifying against the same one
#: means a green tick answers the only question worth asking: will the write-up
#: run? A key that works for another model but not this one is not usable here.
_VERIFY_MODEL = "gemini-3.5-flash-lite"

#: One token from that model. `maxOutputTokens: 1` keeps it to a rounding error
#: on the bill while still exercising generation, which listing never does.
_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_VERIFY_MODEL}:generateContent"
)

_PROBE = {
    "contents": [{"parts": [{"text": "hi"}]}],
    "generationConfig": {"maxOutputTokens": 1},
}

#: A person is watching a "checking…" line, so this is a UI timeout, not a
#: network one. Better to say "could not reach Google" than to hang.
_TIMEOUT_SECONDS = 12

_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_NOT_FOUND = 404
_HTTP_TOO_MANY = 429

#: Google's own sentence, trimmed to something a chat bubble can hold.
_DETAIL_MAX = 160


@dataclass(frozen=True, slots=True)
class VerifyResult:
    """Whether the key works, and what to tell the user when it does not.

    ``reason`` is a translation key so the answer survives into every locale.
    ``ok`` is only True when Google generated something: a network failure is
    not an endorsement, and neither is a key that can only list models.
    ``detail`` carries Google's own explanation when it gives one.
    """

    ok: bool
    reason: str = ""
    detail: str = ""


async def verify_gemini_key(key: str) -> VerifyResult:
    """Check *key* against the Gemini API. Never raises."""
    candidate = key.strip()
    if not candidate:
        return VerifyResult(ok=False, reason="settings.err_empty")

    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            # The key goes in a header rather than the query string: a URL ends
            # up in logs, proxies and error messages, and this one is a secret.
            session.post(_ENDPOINT, headers={"x-goog-api-key": candidate}, json=_PROBE) as response,
        ):
            return await _interpret(response)
    except TimeoutError:
        return VerifyResult(ok=False, reason="settings.err_timeout")
    except aiohttp.ClientError as exc:
        logger.warning("Gemini key check could not reach the API: %s", exc)
        return VerifyResult(ok=False, reason="settings.err_network")
    except asyncio.CancelledError:
        raise
    except Exception:
        # A verification bug must not become "your key is bad".
        logger.exception("Gemini key check failed unexpectedly")
        return VerifyResult(ok=False, reason="settings.err_network")


async def _interpret(response: aiohttp.ClientResponse) -> VerifyResult:
    """Turn an API response into something worth showing a person."""
    if response.status == 200:
        return VerifyResult(ok=True)
    explanation = await _explanation(response)
    if response.status == _HTTP_TOO_MANY:
        # The key is real — it is the quota that is spent. Saying "invalid key"
        # here would send someone off to generate a second one for nothing.
        return VerifyResult(ok=False, reason="settings.err_quota", detail=explanation)
    if response.status in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN, _HTTP_NOT_FOUND) or (
        400 <= response.status < 500
    ):
        # A refusal with a reason is worth repeating verbatim: "your project has
        # been denied access" is a different errand from a mistyped key, and
        # guessing between them is what cost three keys and an evening.
        if explanation:
            return VerifyResult(ok=False, reason="settings.err_refused_detail", detail=explanation)
        return VerifyResult(ok=False, reason="settings.err_rejected")
    return VerifyResult(ok=False, reason="settings.err_upstream", detail=explanation)


async def _explanation(response: aiohttp.ClientResponse) -> str:
    """Google's own message for a failure, when the body carries one."""
    try:
        body = await response.json()
    except (aiohttp.ClientError, ValueError, TypeError):
        return ""
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return ""
    return " ".join(message.split())[:_DETAIL_MAX]
