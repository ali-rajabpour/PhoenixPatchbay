"""When a finished turn writes the handoff up, and when it leaves it alone.

The handoff feature failed silently for weeks: the file existed, the sections
were there, and nothing ever filled them, because consolidation only ran at a
compaction the session never reached.

These tests cover when the write-up runs and which writer does it. The prompt
itself is covered in tests/handoff/test_prompts.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from phoenix_patchbay.handoff.transcript import write_offset
from phoenix_patchbay.orchestrator.flows import (
    _CONSOLIDATE_AFTER_LOG_LINES,
    HANDOFF_WRITER_MODEL,
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
    # A MagicMock attribute is truthy, and truthy here means "use Gemini".
    # Say no explicitly so these stay tests of the in-session path.
    orch._config.gemini_api_key = None
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


# ---------------------------------------------------------------------------
# Which writer does the work
# ---------------------------------------------------------------------------


HANDOFF_DOC = """# Handoff

## Objective
Keep rates.py correct.

## Current state
10% VAT.

## Done
## Next
## Open questions
## Constraints
## Dead ends
## Artifacts
## Log
"""


def _external_orch(tmp_path: Path, *, result: str, api_key: str = "AIza-test") -> MagicMock:
    """An orchestrator configured to hand the write-up to Gemini."""
    orch = _orch(tmp_path, pending_lines=_CONSOLIDATE_AFTER_LOG_LINES)
    orch._config.gemini_api_key = api_key
    orch.paths.claude_home = tmp_path / "claude"
    orch.paths.workspace = tmp_path / "ws"
    orch.bindings.resolve.return_value = tmp_path / "proj"
    orch.handoffs.read.return_value = ""
    orch.handoffs.write.return_value = True
    orch._cli_service.execute = AsyncMock(
        return_value=SimpleNamespace(is_error=False, result=result)
    )

    # A transcript where the writer can find something to write up.
    session_dir = orch.paths.claude_home / "projects" / str(tmp_path / "proj").replace("/", "-")
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "sess-1.jsonl").write_text(
        json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "do a thing"}]}})
        + "\n",
        encoding="utf-8",
    )
    return orch


class TestWriterSelection:
    @pytest.mark.asyncio
    async def test_without_a_key_the_session_writes_itself_up(self, tmp_path: Path) -> None:
        orch = _orch(tmp_path, pending_lines=_CONSOLIDATE_AFTER_LOG_LINES)
        orch._config.gemini_api_key = None

        await _maybe_consolidate(orch, KEY)

        request = orch._cli_service.execute.await_args.args[0]
        assert request.resume_session == "sess-1"
        assert request.provider_override is None

    @pytest.mark.asyncio
    async def test_with_a_key_gemini_writes_it_up_instead(self, tmp_path: Path) -> None:
        orch = _external_orch(tmp_path, result=HANDOFF_DOC)

        await _maybe_consolidate(orch, KEY)

        request = orch._cli_service.execute.await_args.args[0]
        assert request.provider_override == "gemini"
        # Naming the model matters: with none, no --model flag is passed and the
        # Gemini CLI picks its own default, which changes between versions.
        assert request.model_override == HANDOFF_WRITER_MODEL
        # A Claude Code session has one writer. Resuming it from here would
        # collide with the user's next message.
        assert request.resume_session is None
        assert "do a thing" in request.prompt, "the writer was sent no material"

    @pytest.mark.asyncio
    async def test_the_document_is_written_by_us_not_by_the_model(
        self, tmp_path: Path
    ) -> None:
        """A model asked to edit a file can fail in ways that look like success."""
        orch = _external_orch(tmp_path, result=HANDOFF_DOC)

        await _maybe_consolidate(orch, KEY)

        orch.handoffs.write.assert_called_once()
        assert "10% VAT" in orch.handoffs.write.call_args.args[2]

    @pytest.mark.asyncio
    async def test_a_fenced_answer_is_unwrapped(self, tmp_path: Path) -> None:
        orch = _external_orch(tmp_path, result=f"```markdown\n{HANDOFF_DOC}```")

        await _maybe_consolidate(orch, KEY)

        written = orch.handoffs.write.call_args.args[2]
        assert written.startswith("# Handoff")
        assert "```" not in written

    @pytest.mark.asyncio
    async def test_a_refusal_never_overwrites_the_handoff(self, tmp_path: Path) -> None:
        orch = _external_orch(tmp_path, result="NOTHING TO RECORD")

        await _maybe_consolidate(orch, KEY)

        orch.handoffs.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_an_answer_that_is_not_a_handoff_is_refused(self, tmp_path: Path) -> None:
        """Chat instead of a document must not replace a good handoff."""
        orch = _external_orch(tmp_path, result="Sure! Here is what I think you want.")

        await _maybe_consolidate(orch, KEY)

        orch.handoffs.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_an_errored_writer_leaves_the_handoff_alone(self, tmp_path: Path) -> None:
        orch = _external_orch(tmp_path, result="quota exceeded")
        orch._cli_service.execute = AsyncMock(
            return_value=SimpleNamespace(is_error=True, result="quota exceeded")
        )

        await _maybe_consolidate(orch, KEY)

        orch.handoffs.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_nothing_new_in_the_transcript_costs_nothing(self, tmp_path: Path) -> None:
        orch = _external_orch(tmp_path, result=HANDOFF_DOC)
        handoff = tmp_path / "proj" / "handoffs" / "c1-t2.md"
        handoff.parent.mkdir(parents=True, exist_ok=True)
        session_dir = orch.paths.claude_home / "projects" / str(tmp_path / "proj").replace("/", "-")
        write_offset(handoff, (session_dir / "sess-1.jsonl").stat().st_size)

        await _maybe_consolidate(orch, KEY)

        orch._cli_service.execute.assert_not_awaited()


class TestWriterModel:
    """The write-up model is pinned, not configured."""

    def test_it_is_a_concrete_version_not_a_moving_alias(self) -> None:
        """`gemini-flash-latest` would re-point under us without a deploy."""
        assert HANDOFF_WRITER_MODEL.startswith("gemini-")
        assert not HANDOFF_WRITER_MODEL.endswith("-latest")

    def test_it_is_not_reachable_from_settings(self) -> None:
        """Ali's call: the user picks the key, never the model behind it."""
        from phoenix_patchbay.orchestrator.selectors.settings_selector import SETTINGS

        assert all(s.field != "handoff_writer_model" for s in SETTINGS)

    def test_it_is_not_a_config_field(self) -> None:
        from phoenix_patchbay.config import AgentConfig

        assert not hasattr(AgentConfig(allowed_user_ids=[1]), "handoff_writer_model")
