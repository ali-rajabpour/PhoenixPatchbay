"""Switches waiting for the next message to compact them.

Marked when the model or persona changes, spent on the first message after it.
Tapping a picker is not the boundary: browsing models, or correcting a mistap,
must not cost a write-up or end a live session.
"""

from __future__ import annotations

from phoenix_patchbay.handoff.pending_switch import PendingSwitches
from phoenix_patchbay.session.key import SessionKey

KEY = SessionKey.telegram(chat_id=-100, topic_id=556)
OTHER = SessionKey.telegram(chat_id=-100, topic_id=97)


def test_a_marked_switch_is_taken_once() -> None:
    pending = PendingSwitches()
    pending.mark(KEY, "model sonnet -> opus", "sess-1")

    taken = pending.take(KEY)

    assert taken is not None
    assert taken.reason == "model sonnet -> opus"
    assert taken.session_id == "sess-1"
    assert pending.take(KEY) is None


def test_an_unmarked_conversation_owes_nothing() -> None:
    assert PendingSwitches().take(KEY) is None


def test_marks_do_not_leak_between_conversations() -> None:
    pending = PendingSwitches()
    pending.mark(KEY, "model sonnet -> opus", "sess-1")

    assert pending.take(OTHER) is None
    assert pending.take(KEY) is not None


def test_the_first_mark_wins() -> None:
    """Model and persona changed before sending anything is still one boundary.

    The first mark holds the session that did the work; the second would name
    the session the first one is about to end.
    """
    pending = PendingSwitches()
    pending.mark(KEY, "model sonnet -> opus", "sess-1")
    pending.mark(KEY, "persona coder -> web-designer", "")

    taken = pending.take(KEY)

    assert taken is not None
    assert taken.session_id == "sess-1"
    assert taken.reason == "model sonnet -> opus"


def test_clearing_forgets_it() -> None:
    pending = PendingSwitches()
    pending.mark(KEY, "model sonnet -> opus", "sess-1")
    pending.clear(KEY)

    assert pending.take(KEY) is None


def test_a_switch_without_a_session_is_still_recorded() -> None:
    """A persona change knows the conversation, not the session id; the flow resolves it."""
    pending = PendingSwitches()
    pending.mark(KEY, "persona coder -> web-designer")

    taken = pending.take(KEY)

    assert taken is not None
    assert taken.session_id == ""
