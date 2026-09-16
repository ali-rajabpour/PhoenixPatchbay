"""Reading a conversation for a writer that was not in it."""

from __future__ import annotations

import json
from pathlib import Path

from phoenix_patchbay.handoff.transcript import (
    MAX_MESSAGE_CHARS,
    read_offset,
    read_since,
    transcript_path,
    write_offset,
)


def _jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def _msg(role: str, text: str) -> dict:
    return {"type": role, "message": {"content": [{"type": "text", "text": text}]}}


def test_path_matches_claude_codes_layout() -> None:
    """A wrong slug reads nothing and looks exactly like a quiet conversation."""
    got = transcript_path(Path("/home/p/.claude"), "/home/p/IT/site", "abc")
    assert got == Path("/home/p/.claude/projects/-home-p-IT-site/abc.jsonl")


class TestSlicing:
    def test_reads_only_what_is_new(self, tmp_path: Path) -> None:
        t = tmp_path / "s.jsonl"
        _jsonl(t, [_msg("user", "first thing"), _msg("assistant", "did it")])
        first = read_since(t, 0)
        assert "first thing" in first.text

        with t.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_msg("user", "second thing")) + "\n")

        second = read_since(t, first.offset)
        assert "second thing" in second.text
        assert "first thing" not in second.text, "already written up, paid for twice"

    def test_nothing_new_is_empty(self, tmp_path: Path) -> None:
        t = tmp_path / "s.jsonl"
        _jsonl(t, [_msg("user", "hello")])
        assert read_since(t, read_since(t, 0).offset).text == ""

    def test_a_replaced_transcript_restarts(self, tmp_path: Path) -> None:
        """A cleared session leaves an offset pointing past a shorter file."""
        t = tmp_path / "s.jsonl"
        _jsonl(t, [_msg("user", "brand new conversation")])
        assert "brand new conversation" in read_since(t, 99_999).text

    def test_a_missing_transcript_is_not_an_error(self, tmp_path: Path) -> None:
        assert read_since(tmp_path / "gone.jsonl", 0).text == ""

    def test_a_half_written_line_is_skipped(self, tmp_path: Path) -> None:
        t = tmp_path / "s.jsonl"
        t.write_text(json.dumps(_msg("user", "complete")) + '\n{"type": "user", ', encoding="utf-8")
        assert "complete" in read_since(t, 0).text  # and no exception


class TestWhatIsKept:
    def test_tool_results_are_dropped_but_tool_names_survive(self, tmp_path: Path) -> None:
        """Results are the bulk of a transcript; the handoff wants the decision."""
        t = tmp_path / "s.jsonl"
        _jsonl(
            t,
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "text", "text": "Editing the rate."},
                            {"type": "tool_use", "name": "Edit", "input": {"x": "y"}},
                        ]
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "content": "MASSIVE" * 5000,
                                "tool_use_id": "t1",
                            }
                        ]
                    },
                },
            ],
        )
        text = read_since(t, 0).text
        assert "Editing the rate." in text
        assert "[used Edit]" in text
        assert "MASSIVE" not in text

    def test_a_very_long_message_is_truncated(self, tmp_path: Path) -> None:
        t = tmp_path / "s.jsonl"
        _jsonl(t, [_msg("assistant", "x" * (MAX_MESSAGE_CHARS * 3))])
        text = read_since(t, 0).text
        assert len(text) < MAX_MESSAGE_CHARS * 2
        assert "[…]" in text


class TestWatermark:
    def test_round_trip(self, tmp_path: Path) -> None:
        handoff = tmp_path / "c1-t2.md"
        assert read_offset(handoff, "sess-1") == 0
        write_offset(handoff, "sess-1", 1234)
        assert read_offset(handoff, "sess-1") == 1234

    def test_it_hides_beside_the_handoff(self, tmp_path: Path) -> None:
        """`handoffs/` is git-excluded as a directory, so a dotfile in it is too."""
        handoff = tmp_path / "c1-t2.md"
        write_offset(handoff, "sess-1", 5)
        assert (tmp_path / ".c1-t2.offset").is_file()

    def test_an_unreadable_watermark_means_start_over(self, tmp_path: Path) -> None:
        handoff = tmp_path / "c1-t2.md"
        (tmp_path / ".c1-t2.offset").write_text("not a number", encoding="utf-8")
        assert read_offset(handoff, "sess-1") == 0

    def test_another_sessions_watermark_is_not_applied(self, tmp_path: Path) -> None:
        """A byte count only means something inside the file it was measured in.

        Applying the old session's count to a new transcript skipped the start of
        it, which in production hid an entire task from the write-up.
        """
        handoff = tmp_path / "c1-t2.md"
        write_offset(handoff, "old-session", 9_000)

        assert read_offset(handoff, "new-session") == 0

    def test_a_legacy_bare_number_is_ignored(self, tmp_path: Path) -> None:
        """Pre-2026-09 watermarks carry no id, so there is no telling whose they are."""
        handoff = tmp_path / "c1-t2.md"
        (tmp_path / ".c1-t2.offset").write_text("109231\n", encoding="utf-8")

        assert read_offset(handoff, "sess-1") == 0
