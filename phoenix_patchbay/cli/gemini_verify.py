"""Ask Google whether a key works, instead of guessing from its shape.

A regex can only say "that looks like a key". It rejects a valid key whose
format changed, accepts a revoked one, and tells the user off for a typo it
cannot actually see. The API knows the answer, so ask it: one unauthenticated
GET that lists models, which costs no tokens and returns in well under a
second.

Failure is reported in the user's terms — wrong key, no quota, no network —
because "HTTP 400" is not something anyone can act on.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)

#: Listing models is the cheapest authenticated call the API has: no tokens,
#: no model chosen, and it fails exactly when the key is unusable.
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

#: A person is watching a "checking…" line, so this is a UI timeout, not a
#: network one. Better to say "could not reach Google" than to hang.
_TIMEOUT_SECONDS = 12

_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_TOO_MANY = 429


@dataclass(frozen=True, slots=True)
class VerifyResult:
    """Whether the key works, and what to tell the user when it does not.

    ``reason`` is a translation key so the answer survives into every locale.
    ``ok`` is only True when Google accepted the key: a network failure is not
    an endorsement, and storing an unverified key would defeat the check.
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
            session.get(_ENDPOINT, headers={"x-goog-api-key": candidate}) as response,
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
        return VerifyResult(ok=True, detail=await _model_count(response))
    if response.status in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
        return VerifyResult(ok=False, reason="settings.err_rejected")
    if response.status == _HTTP_TOO_MANY:
        # The key is real — it is the quota that is spent. Saying "invalid key"
        # here would send someone off to generate a second one for nothing.
        return VerifyResult(ok=False, reason="settings.err_quota")
    if 400 <= response.status < 500:
        return VerifyResult(ok=False, reason="settings.err_rejected")
    return VerifyResult(ok=False, reason="settings.err_upstream")


async def _model_count(response: aiohttp.ClientResponse) -> str:
    """How many models the key can reach — evidence, not just a green tick."""
    try:
        body = await response.json()
    except (aiohttp.ClientError, ValueError):
        return ""
    models = body.get("models") if isinstance(body, dict) else None
    return str(len(models)) if isinstance(models, list) else ""
