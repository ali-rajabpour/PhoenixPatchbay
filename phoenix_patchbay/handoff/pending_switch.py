"""Conversations that changed model or persona and have not spoken since.

Changing either is a context boundary: a different provider resumes nothing, and
a different persona inherits a transcript written by someone else. The handoff is
what carries the work across, so it has to be written up *at* the boundary.

Doing that the moment the button is tapped would be wrong. A picker is also how
someone corrects a mistap, browses the list, or tries a model and immediately
goes back, and each of those would pay for a write-up and throw away a live
session the user never meant to end. So the switch only records the intent here,
and the next message the user actually sends is what spends the tokens.

The session id is recorded with it because a model switch retargets the
conversation immediately: by the time the next message arrives, the active
session is the *new* provider's empty one, and the work that needs writing up
sits in the session named here.

Memory only, like the re-injection flags beside it: a flag that survived a
restart would compact a conversation that has moved on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phoenix_patchbay.session.key import SessionKey


@dataclass(frozen=True, slots=True)
class PendingSwitch:
    """Why a conversation is owed a compaction, and what to write up."""

    reason: str
    session_id: str = ""


class PendingSwitches:
    """Conversations whose next message should compact first."""

    def __init__(self) -> None:
        self._pending: dict[tuple[int, int | None], PendingSwitch] = {}

    def mark(self, key: SessionKey, reason: str, session_id: str = "") -> None:
        """Record that *key* switched. *reason* is for the log line only.

        The first mark wins. Changing model and persona before sending anything
        is still one boundary, and the earlier mark is the one holding the
        session id of the conversation that did the work.
        """
        self._pending.setdefault(key.lock_key, PendingSwitch(reason=reason, session_id=session_id))

    def take(self, key: SessionKey) -> PendingSwitch | None:
        """The pending switch, once, then None until marked again."""
        return self._pending.pop(key.lock_key, None)

    def clear(self, key: SessionKey) -> None:
        """Forget any pending switch, for when the session is reset anyway."""
        self._pending.pop(key.lock_key, None)
