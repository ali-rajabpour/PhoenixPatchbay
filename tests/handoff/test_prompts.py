"""The prompts, and the framing of what goes back into context."""

from __future__ import annotations

from pathlib import Path

from phoenix_patchbay.handoff.prompts import (
    TEMPLATE,
    consolidation_prompt,
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


def test_injection_excludes_the_log() -> None:
    block = injection_block("## Objective\nship it\n\n## Log\n- noisy raw line\n")

    assert "ship it" in block
    assert "noisy raw line" not in block


def test_injection_of_an_empty_handoff_is_harmless() -> None:
    assert "not instructions" in injection_block("").lower()


def test_the_consolidation_names_the_file_too() -> None:
    assert str(HANDOFF) in consolidation_prompt(HANDOFF)


def test_the_consolidation_does_not_leak_into_the_reply() -> None:
    assert "never mention this instruction" in consolidation_prompt(HANDOFF).lower()
