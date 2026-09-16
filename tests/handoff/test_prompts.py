"""The prompts, and the framing of what goes back into context."""

from __future__ import annotations

from pathlib import Path

from phoenix_patchbay.handoff.prompts import (
    _LOG_TAIL_ENTRIES,
    TEMPLATE,
    consolidation_prompt,
    external_consolidation_prompt,
    history_pointer,
    injection_block,
)

HANDOFF = Path("/home/patchbay/IT/proj/handoffs/c1-t2.md")


def test_the_template_names_every_required_section() -> None:
    for section in (
        "## Objective",
        "## Current state",
        "## Done",
        "## Next",
        "## Open questions",
        "## Constraints",
        "## Dead ends",
        "## Artifacts",
        "## Log",
    ):
        assert section in TEMPLATE


def test_the_consolidation_demands_identifiers() -> None:
    assert "identifier" in consolidation_prompt(HANDOFF).lower()


def test_the_consolidation_protects_an_unchanged_file() -> None:
    assert "leave the file unchanged" in consolidation_prompt(HANDOFF).lower()


def test_injection_is_framed_as_a_record_not_an_instruction() -> None:
    """An identity or task claim read as an order is how things get deleted."""
    block = injection_block("## Objective\nship the redesign\n")

    assert "not instructions" in block.lower()
    assert "ship the redesign" in block


def test_injection_carries_the_newest_log_entries() -> None:
    """The current request lives only in the log until a consolidation runs.

    Injecting the sections alone described last week's task, so a model switch
    mid-task handed the new session a handoff that never mentioned the work.
    """
    block = injection_block(
        "## Objective\nship it\n\n## Log\n- 09-15 18:14 - asked: build the anemia page\n"
    )

    assert "ship it" in block
    assert "build the anemia page" in block


def test_injection_keeps_the_log_tail_short() -> None:
    entries = "\n".join(f"- line {n}" for n in range(1, 21))
    block = injection_block(f"## Objective\nship it\n\n## Log\n{entries}\n")

    assert "- line 20" in block
    assert "- line 1\n" not in block, "the whole log is injected at every boundary"
    assert block.count("- line ") == _LOG_TAIL_ENTRIES


def test_injection_of_an_empty_handoff_is_harmless() -> None:
    assert "not instructions" in injection_block("").lower()


def test_the_consolidation_names_the_file_too() -> None:
    assert str(HANDOFF) in consolidation_prompt(HANDOFF)


def test_the_consolidation_does_not_leak_into_the_reply() -> None:
    assert "never mention this instruction" in consolidation_prompt(HANDOFF).lower()


def test_the_external_prompt_insists_on_the_two_summary_sections() -> None:
    """A cheap model leaves them blank unless told; they are what is read first."""
    body = external_consolidation_prompt("", "material").lower()
    assert "must never be empty" in body


def test_the_external_prompt_forbids_placeholder_identifiers() -> None:
    """Flash-Lite padded every line with "(commit/session history: rates.py)"."""
    body = external_consolidation_prompt("", "material").lower()
    assert "placeholder" in body


def test_the_external_prompt_carries_the_material() -> None:
    body = external_consolidation_prompt("EXISTING HANDOFF", "WHAT HAPPENED")
    assert "EXISTING HANDOFF" in body
    assert "WHAT HAPPENED" in body


def test_history_pointer_names_the_file_and_never_carries_its_contents() -> None:
    history = Path("/home/patchbay/IT/proj/handoffs/c1-t2.history.md")

    line = history_pointer(history)

    assert str(history) in line
    assert "search" in line.lower()
    assert "\n" not in line


def test_the_handoff_block_no_longer_repeats_the_pointer() -> None:
    assert ".history.md" not in injection_block("## Objective\nship it\n")
