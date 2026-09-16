"""Compacting at the first message after a model or persona switch.

The failure this prevents, from production on 2026-09-15: a topic switched from
one provider to another mid-task, the new provider resumed nothing, the handoff
in front of it still described the previous week's work, and the session asked
the user what it should be doing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from phoenix_patchbay.handoff.pending_switch import PendingSwitches
from phoenix_patchbay.handoff.reinject import ReinjectFlags
from phoenix_patchbay.orchestrator.flows import (
    _compact_after_switch,
    _consolidate_externally,
    _WriteUp,
)
from phoenix_patchbay.session.key import SessionKey

if TYPE_CHECKING:
    import pytest

KEY = SessionKey.telegram(chat_id=-100, topic_id=556)


def _orch(tmp_path: Path, *, active_session_id: str = "", has_content: bool = True) -> MagicMock:
    orch = MagicMock()
    orch.bindings.resolve.return_value = None
    orch.pending_switch = PendingSwitches()
    orch.reinject = ReinjectFlags()
    orch.handoffs.has_content.return_value = has_content
    orch._sessions.get_active = AsyncMock(
        return_value=SimpleNamespace(session_id=active_session_id)
    )
    orch._cli_service.execute = AsyncMock(return_value=SimpleNamespace(is_error=False))
    orch._process_registry.kill_by_chat_topic = AsyncMock()
    orch.reset_active_provider_session = AsyncMock()
    orch.paths.patchbay_home = tmp_path
    # No transcript under these, so the off-session writers fall through to the
    # in-session one, which is what these tests are about.
    orch.paths.claude_home = tmp_path / "claude"
    orch.paths.workspace = tmp_path / "ws"
    orch._config.gemini_api_key = None
    return orch


class TestWhenItFires:
    async def test_writes_up_the_session_that_did_the_work(self, tmp_path: Path) -> None:
        """A model switch retargets the conversation, so the active session is the new, empty one."""
        orch = _orch(tmp_path, active_session_id="")
        orch.pending_switch.mark(KEY, "model sonnet -> 9router/coder", "worked-session")

        await _compact_after_switch(orch, KEY)

        request = orch._cli_service.execute.await_args.args[0]
        assert request.resume_session == "worked-session"

    async def test_ends_the_session_and_owes_a_re_injection(self, tmp_path: Path) -> None:
        orch = _orch(tmp_path, active_session_id="")
        orch.pending_switch.mark(KEY, "model sonnet -> opus", "worked-session")

        await _compact_after_switch(orch, KEY)

        orch.reset_active_provider_session.assert_awaited_once()
        orch._process_registry.kill_by_chat_topic.assert_awaited_once()
        assert orch.reinject.take(KEY), "the new session would never be shown the handoff"

    async def test_a_persona_switch_uses_the_live_session(self, tmp_path: Path) -> None:
        """Changing persona keeps the provider, so the active session is the one to write up."""
        orch = _orch(tmp_path, active_session_id="live-session")
        orch.pending_switch.mark(KEY, "persona coder -> web-designer")

        await _compact_after_switch(orch, KEY)

        request = orch._cli_service.execute.await_args.args[0]
        assert request.resume_session == "live-session"


class TestWhenItDoesNot:
    async def test_nothing_pending_is_a_no_op(self, tmp_path: Path) -> None:
        orch = _orch(tmp_path, active_session_id="live-session")

        await _compact_after_switch(orch, KEY)

        orch._cli_service.execute.assert_not_awaited()
        orch.reset_active_provider_session.assert_not_awaited()

    async def test_a_switch_with_no_session_costs_nothing(self, tmp_path: Path) -> None:
        """Switching before the first message has no context to carry across."""
        orch = _orch(tmp_path, active_session_id="")
        orch.pending_switch.mark(KEY, "model sonnet -> opus", "")

        await _compact_after_switch(orch, KEY)

        orch._cli_service.execute.assert_not_awaited()
        orch.reset_active_provider_session.assert_not_awaited()

    async def test_the_session_is_kept_when_no_handoff_was_produced(self, tmp_path: Path) -> None:
        """Ending a session with nothing written down is just losing the conversation."""
        orch = _orch(tmp_path, active_session_id="", has_content=False)
        orch.pending_switch.mark(KEY, "model sonnet -> opus", "worked-session")

        await _compact_after_switch(orch, KEY)

        orch.reset_active_provider_session.assert_not_awaited()
        assert not orch.reinject.take(KEY)

    async def test_it_only_fires_once_per_switch(self, tmp_path: Path) -> None:
        orch = _orch(tmp_path, active_session_id="")
        orch.pending_switch.mark(KEY, "model sonnet -> opus", "worked-session")

        await _compact_after_switch(orch, KEY)
        await _compact_after_switch(orch, KEY)

        orch._cli_service.execute.assert_awaited_once()


class TestFailureIsExplained:
    async def test_the_writers_error_reaches_the_log(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A 403 from the write-up provider used to log an empty message."""
        orch = _orch(tmp_path)
        orch._config.gemini_api_key = "key"
        orch.handoffs.read.return_value = "## Objective\nship it\n"
        orch._cli_service.execute = AsyncMock(
            return_value=SimpleNamespace(is_error=True, result="", returncode=1, timed_out=False)
        )
        session_dir = tmp_path / "projects" / str(tmp_path.parent).replace("/", "-")
        orch.paths.claude_home = tmp_path
        orch.paths.workspace = tmp_path.parent
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "sess-1.jsonl").write_text(
            '{"type": "user", "message": {"content": [{"type": "text", "text": "do the thing"}]}}\n',
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            outcome = await _consolidate_externally(
                orch, KEY, "sess-1", provider="gemini", model="gemini-3.5-flash-lite"
            )
        assert outcome is _WriteUp.FAILED

        message = " ".join(record.getMessage() for record in caplog.records)
        assert "rc=1" in message
        assert "no output from the provider CLI" in message
