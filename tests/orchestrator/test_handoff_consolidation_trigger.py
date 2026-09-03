"""When a finished turn writes the handoff up, and when it leaves it alone.

The handoff feature failed silently for weeks: the file existed, the sections
were there, and nothing ever filled them, because consolidation only ran at a
compaction the session never reached. These tests are about the trigger, not
the prompt — the prompt was always fine.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from phoenix_patchbay.orchestrator.flows import (
    _CONSOLIDATE_AFTER_LOG_LINES,
    _maybe_consolidate,
)
from phoenix_patchbay.session.key import SessionKey


def _orch(
    tmp_path: Path,
    *,
    pending_lines: int,
    queued: bool = False,
    session_id: str | None = "sess-1",
) -> MagicMock:
    orch = MagicMock()
    orch.bindings.resolve.return_value = None
    orch.handoffs.pending_log_lines.return_value = pending_lines
    orch.has_queued_work.return_value = queued
    session = SimpleNamespace(session_id=session_id) if session_id is not None else None
    orch._sessions.get_active = AsyncMock(return_value=session)
    orch._cli_service.execute = AsyncMock(return_value=SimpleNamespace(is_error=False))
    orch.paths.patchbay_home = tmp_path
    return orch


KEY = SessionKey.telegram(1, 2)


class TestWhenItFires:
    @pytest.mark.asyncio
    async def test_consolidates_once_enough_has_happened(self, tmp_path: Path) -> None:
        orch = _orch(tmp_path, pending_lines=_CONSOLIDATE_AFTER_LOG_LINES)

        await _maybe_consolidate(orch, KEY)

        orch._cli_service.execute.assert_awaited_once()
        request = orch._cli_service.execute.await_args.args[0]
        assert request.process_label == "handoff_consolidation"
        # It must resume the conversation being written up, not start a new one:
        # a fresh session knows nothing and would produce an empty handoff.
        assert request.resume_session == "sess-1"

    @pytest.mark.asyncio
    async def test_does_not_fire_before_there_is_enough_to_say(self, tmp_path: Path) -> None:
        orch = _orch(tmp_path, pending_lines=_CONSOLIDATE_AFTER_LOG_LINES - 1)

        await _maybe_consolidate(orch, KEY)

        orch._cli_service.execute.assert_not_awaited()


class TestWhenItHoldsOff:
    @pytest.mark.asyncio
    async def test_a_queued_message_means_the_task_is_not_over(self, tmp_path: Path) -> None:
        """Mid-task is the wrong moment, and it would make the user wait."""
        orch = _orch(tmp_path, pending_lines=_CONSOLIDATE_AFTER_LOG_LINES + 5, queued=True)

        await _maybe_consolidate(orch, KEY)

        orch._cli_service.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_session_to_resume_is_not_an_error(self, tmp_path: Path) -> None:
        orch = _orch(tmp_path, pending_lines=_CONSOLIDATE_AFTER_LOG_LINES, session_id=None)

        await _maybe_consolidate(orch, KEY)

        orch._cli_service.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_consolidation_does_not_raise(self, tmp_path: Path) -> None:
        """It runs at the end of the user's turn; it must never cost them one."""
        orch = _orch(tmp_path, pending_lines=_CONSOLIDATE_AFTER_LOG_LINES)
        orch._cli_service.execute = AsyncMock(side_effect=OSError("cli gone"))

        await _maybe_consolidate(orch, KEY)  # must not raise


class TestThePendingWatermark:
    """`pending_log_lines` is what decides all of the above."""

    def test_counts_only_entries_below_the_log_heading(self, tmp_path: Path) -> None:
        from phoenix_patchbay.handoff.store import HandoffStore

        paths = MagicMock()
        paths.patchbay_home = tmp_path
        store = HandoffStore(paths)
        store.write(
            KEY,
            None,
            "# Handoff\n\n## Done\n- a finished thing\n- another\n\n## Log\n- one\n- two\n",
        )

        assert store.pending_log_lines(KEY, None) == 2

    def test_an_empty_log_means_nothing_is_owed(self, tmp_path: Path) -> None:
        from phoenix_patchbay.handoff.store import HandoffStore

        paths = MagicMock()
        paths.patchbay_home = tmp_path
        store = HandoffStore(paths)
        store.write(KEY, None, "# Handoff\n\n## Done\n- written up already\n\n## Log\n")

        assert store.pending_log_lines(KEY, None) == 0
