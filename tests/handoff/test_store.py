"""Reading, writing and archiving handoffs."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from phoenix_patchbay.handoff.store import HandoffStore
from phoenix_patchbay.session.key import SessionKey

KEY = SessionKey.telegram(chat_id=-100, topic_id=110)
OTHER = SessionKey.telegram(chat_id=-100, topic_id=97)


def _store(tmp_path: Path) -> HandoffStore:
    return HandoffStore(SimpleNamespace(patchbay_home=tmp_path / ".phoenix-patchbay"))


def _folder(tmp_path: Path) -> Path:
    folder = tmp_path / "proj"
    folder.mkdir(exist_ok=True)
    return folder


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)

    assert store.write(KEY, folder, "# Handoff\n\n## Objective\nship it\n")

    assert "ship it" in store.read(KEY, folder)


def test_reading_a_missing_handoff_is_empty(tmp_path: Path) -> None:
    assert _store(tmp_path).read(KEY, _folder(tmp_path)) == ""


def test_archive_moves_the_file_out_of_the_folder(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "## Objective\nwebsite redesign\n")

    archived = store.archive(KEY, folder)

    assert archived is not None
    assert archived.exists()
    assert not (folder / "handoffs" / "c100-t110.md").exists()
    assert "website redesign" in archived.read_text(encoding="utf-8")
    assert folder not in archived.parents


def test_archiving_nothing_is_not_an_error(tmp_path: Path) -> None:
    assert _store(tmp_path).archive(KEY, _folder(tmp_path)) is None


def test_archives_are_listed_newest_first_and_scoped(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "## Objective\nfirst task\n")
    store.archive(KEY, folder)
    store.write(KEY, folder, "## Objective\nsecond task\n")
    store.archive(KEY, folder)
    store.write(OTHER, folder, "## Objective\nsomeone elses topic\n")
    store.archive(OTHER, folder)

    found = store.list_archives(KEY)

    assert len(found) == 2
    bodies = [p.read_text(encoding="utf-8") for p in found]
    assert all("someone elses topic" not in b for b in bodies)


def test_an_empty_consolidation_never_replaces_a_good_handoff(tmp_path: Path) -> None:
    """A model returning nothing is a failed turn, not an order to forget."""
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "## Objective\nreal work\n")

    assert not store.write(KEY, folder, "   \n")

    assert "real work" in store.read(KEY, folder)


def test_a_write_into_a_repo_is_protected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    subprocess.run(["git", "init", "-q", str(folder)], check=True)

    assert store.write(KEY, folder, "## Objective\nship it\n")

    exclude = (folder / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert "handoffs/" in exclude


def test_an_unbound_conversation_writes_under_patchbay_home(tmp_path: Path) -> None:
    store = _store(tmp_path)
    general = SessionKey.telegram(chat_id=-100)

    assert store.write(general, None, "## Objective\ngeneral chatter\n")

    assert "general chatter" in store.read(general, None)


def test_the_skeleton_is_created_by_code_not_by_asking(tmp_path: Path) -> None:
    """The model was asked to create the file, received the instruction, and
    made eleven tool calls without writing it. Existence is code's job."""
    store = _store(tmp_path)
    folder = _folder(tmp_path)

    assert store.ensure_exists(KEY, folder)

    assert "## Objective" in store.read(KEY, folder)


def test_a_bare_skeleton_does_not_count_as_a_handoff(tmp_path: Path) -> None:
    """Otherwise /handoff shows empty headings and /compact carries nothing."""
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.ensure_exists(KEY, folder)

    assert not store.has_content(KEY, folder)


def test_content_under_a_heading_counts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nship the redesign\n")

    assert store.has_content(KEY, folder)


def test_ensure_exists_never_overwrites_real_content(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "## Objective\nreal work in progress\n")

    store.ensure_exists(KEY, folder)

    assert "real work in progress" in store.read(KEY, folder)


def test_a_turn_is_logged_without_asking_the_model(tmp_path: Path) -> None:
    """The model was told the path, the sections and the rule, and across three
    turns wrote nothing. Facts code can vouch for get recorded by code."""
    store = _store(tmp_path)
    folder = _folder(tmp_path)

    assert store.append_log(KEY, folder, "- 2026-08-31 09:00 — asked: rebuild the About page")

    body = store.read(KEY, folder)
    assert "rebuild the About page" in body
    assert store.has_content(KEY, folder)


def test_log_lines_accumulate_in_order(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)

    store.append_log(KEY, folder, "- first")
    store.append_log(KEY, folder, "- second")

    body = store.read(KEY, folder)
    assert body.index("- first") < body.index("- second")


def test_logging_creates_the_handoff_when_missing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)

    assert store.append_log(KEY, folder, "- only line")

    assert "## Objective" in store.read(KEY, folder)


def test_logging_leaves_the_sections_above_it_alone(tmp_path: Path) -> None:
    """A log append must never disturb consolidated state."""
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nship the redesign\n\n## Log\n")

    store.append_log(KEY, folder, "- new line")

    body = store.read(KEY, folder)
    assert "ship the redesign" in body
    assert body.index("ship the redesign") < body.index("- new line")


def test_history_keeps_a_revision_the_handoff_no_longer_holds(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nport the pine strategy\n")

    assert store.append_revision(KEY, folder, "consolidation")
    store.write(KEY, folder, "# Handoff\n\n## Objective\nsomething else entirely\n")

    history = store.history_path(KEY, folder)
    assert history is not None
    body = history.read_text(encoding="utf-8")
    assert "port the pine strategy" in body
    assert "port the pine strategy" not in store.read(KEY, folder)


def test_history_grows_and_never_replaces(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)

    for objective in ("first", "second", "third"):
        store.write(KEY, folder, f"# Handoff\n\n## Objective\n{objective}\n")
        assert store.append_revision(KEY, folder, "consolidation")

    body = store.history_path(KEY, folder).read_text(encoding="utf-8")
    assert body.count("<!-- revision ") == 3
    assert all(word in body for word in ("first", "second", "third"))


def test_an_unchanged_handoff_is_not_recorded_twice(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nship it\n")

    assert store.append_revision(KEY, folder, "consolidation")
    assert not store.append_revision(KEY, folder, "consolidation")

    assert store.history_path(KEY, folder).read_text(encoding="utf-8").count("<!-- revision ") == 1


def test_history_is_separate_per_conversation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nmine\n")
    store.write(OTHER, folder, "# Handoff\n\n## Objective\ntheirs\n")

    store.append_revision(KEY, folder, "consolidation")
    store.append_revision(OTHER, folder, "consolidation")

    assert "theirs" not in store.history_path(KEY, folder).read_text(encoding="utf-8")


def test_there_is_no_history_before_the_first_revision(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nship it\n")

    assert store.history_path(KEY, folder) is None


def test_history_survives_an_archive(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nwork worth keeping\n")

    store.archive(KEY, folder)

    history = store.history_path(KEY, folder)
    assert history is not None
    assert "work worth keeping" in history.read_text(encoding="utf-8")


def test_history_is_refused_when_git_would_track_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    folder = _folder(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=folder, check=True)
    store.write(KEY, folder, "# Handoff\n\n## Objective\nship it\n")

    # A tracked file is not ignored, whatever the exclude file says — which is
    # exactly the case the guard exists for.
    history = folder / "handoffs" / "c100-t110.history.md"
    history.write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "-f", str(history)], cwd=folder, check=True)

    assert not store.append_revision(KEY, folder, "consolidation")
