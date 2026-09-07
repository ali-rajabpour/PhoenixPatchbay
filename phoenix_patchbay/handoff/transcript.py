"""Reading what happened in a conversation, for a writer that was not there.

The in-session consolidation can simply resume: the model already holds the
conversation. A writer running on another provider holds nothing, so it has to
be handed the material — and handing it the whole transcript would cost more
than the write-up saves, and would cost more every day as the session grows.

So the slice is bounded twice: only what has happened since the last write-up
(a byte offset kept beside the handoff), and only the shape of it — who said
what, and which tools ran. Tool *results* are dropped on purpose. They are the
bulk of a transcript by a wide margin, and a handoff records decisions, not the
output of every grep.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: Ceiling on one slice. Past this the tail is kept: the end of a session is
#: what a handoff is about, and the beginning is already written up.
MAX_SLICE_CHARS = 60_000

#: One assistant message can be an essay. Enough to see the decision, not the prose.
MAX_MESSAGE_CHARS = 2_000


@dataclass(frozen=True, slots=True)
class Slice:
    """Rendered conversation since the last write-up, and where to resume."""

    text: str
    offset: int


def transcript_path(claude_home: Path, working_dir: str, session_id: str) -> Path:
    """Where Claude Code keeps this session's JSONL.

    The project directory is the working directory with every separator turned
    into a dash, so ``/home/x/IT/site`` becomes ``-home-x-IT-site``.
    """
    slug = working_dir.replace("/", "-")
    return claude_home / "projects" / slug / f"{session_id}.jsonl"


def _text_of(content: object) -> str:
    """The human-readable part of a message body, ignoring tool payloads."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            parts.append(str(block.get("text", "")))
        elif kind == "tool_use":
            # The name is the useful part: "ran Edit" belongs in a handoff, the
            # diff does not.
            parts.append(f"[used {block.get('name', 'a tool')}]")
    return "\n".join(p for p in parts if p)


def read_since(path: Path, offset: int) -> Slice:
    """Render the transcript from *offset* onwards. Empty when there is nothing."""
    try:
        size = path.stat().st_size
    except OSError:
        return Slice(text="", offset=offset)

    if offset > size:
        # The file was replaced — a cleared session, a restored backup. Starting
        # over is right: the old offset points into a different conversation.
        logger.info("Transcript %s shrank; restarting from the beginning", path)
        offset = 0
    if offset == size:
        return Slice(text="", offset=offset)

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            raw = handle.read()
            new_offset = size
    except OSError as exc:
        logger.warning("Cannot read transcript %s: %s", path, exc)
        return Slice(text="", offset=offset)

    text = _render(raw)
    if len(text) > MAX_SLICE_CHARS:
        text = "[…earlier of this slice omitted…]\n\n" + text[-MAX_SLICE_CHARS:]
    return Slice(text=text, offset=new_offset)


def _render(raw: str) -> str:
    """Turn JSONL records into the who-said-what a write-up needs."""
    lines = []
    for row in raw.splitlines():
        stripped = row.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except ValueError:
            continue  # a partial line at the tail; the next pass will get it
        role = record.get("type")
        if role not in ("user", "assistant"):
            continue
        body = _text_of((record.get("message") or {}).get("content"))
        if not body.strip():
            continue
        if len(body) > MAX_MESSAGE_CHARS:
            body = body[:MAX_MESSAGE_CHARS] + " […]"
        lines.append(f"{role.upper()}: {body}")
    return "\n\n".join(lines)


def offset_path(handoff: Path) -> Path:
    """Where the watermark lives: beside its handoff, hidden, already git-ignored."""
    return handoff.with_name(f".{handoff.stem}.offset")


def read_offset(handoff: Path) -> int:
    try:
        return int(offset_path(handoff).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def write_offset(handoff: Path, offset: int) -> None:
    """Record the watermark. Failure costs a repeated slice, never a lost one."""
    try:
        offset_path(handoff).write_text(f"{offset}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot record handoff offset for %s: %s", handoff, exc)
