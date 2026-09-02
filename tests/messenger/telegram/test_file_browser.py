"""Tests for the interactive file browser.

Rewritten for token addressing: callback data used to carry a relative path,
which overflowed Telegram's 64-byte cap on deep trees. Paths are now addressed
by an opaque token, so the traversal cases below assert that a token resolving
outside the allowed roots is refused — a crafted "../" string is no longer
expressible in callback data at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phoenix_patchbay.files import path_tokens
from phoenix_patchbay.i18n import init
from phoenix_patchbay.messenger.telegram.file_browser import (
    SF_FILE_PREFIX,
    SF_PREFIX,
    file_browser_start,
    handle_file_browser_callback,
    is_file_browser_callback,
)
from phoenix_patchbay.workspace.paths import PatchbayPaths


@pytest.fixture(autouse=True)
def _clean() -> None:
    path_tokens.clear()
    init("en")


@pytest.fixture
def paths(tmp_path: Path) -> PatchbayPaths:
    home = tmp_path / "patchbay"
    home.mkdir()

    (home / "config").mkdir()
    (home / "config" / "config.json").write_text("{}")
    (home / "workspace").mkdir()
    (home / "workspace" / "skills").mkdir()
    (home / "workspace" / "tools").mkdir()
    (home / "workspace" / "CLAUDE.md").write_text("# rules")
    (home / "sessions.json").write_text("[]")

    # Hidden entries and caches must never be listed.
    (home / ".hidden_file").write_text("secret")
    (home / ".hidden_dir").mkdir()
    (home / "workspace" / "__pycache__").mkdir()

    return PatchbayPaths(patchbay_home=home)


def _buttons(kb) -> list:
    return [b for row in kb.inline_keyboard for b in row]


def _open(paths: PatchbayPaths, target: Path):
    return handle_file_browser_callback(paths, {}, f"{SF_PREFIX}{path_tokens.token_for(target)}")


# -- callback matching ---------------------------------------------------------


class TestCallbackMatching:
    def test_matches_own_prefixes(self) -> None:
        for prefix in (SF_PREFIX, SF_FILE_PREFIX, "sf@"):
            assert is_file_browser_callback(f"{prefix}abc")

    def test_ignores_other_namespaces(self) -> None:
        assert not is_file_browser_callback("ms:p:claude")
        assert not is_file_browser_callback("acc:0")


# -- navigation ----------------------------------------------------------------


class TestDirectoryNavigation:
    @pytest.mark.asyncio
    async def test_root_view_lists_the_patchbay_home(self, paths: PatchbayPaths) -> None:
        _text, kb = await file_browser_start(paths, {})
        assert "~/.phoenix-patchbay/" in [b.text for b in _buttons(kb)]

    @pytest.mark.asyncio
    async def test_opening_home_lists_children(self, paths: PatchbayPaths) -> None:
        action = await _open(paths, paths.patchbay_home)
        assert "config/" in action.text
        assert "workspace/" in action.text
        assert "sessions.json" in action.text

    @pytest.mark.asyncio
    async def test_hidden_and_cache_entries_are_excluded(self, paths: PatchbayPaths) -> None:
        action = await _open(paths, paths.patchbay_home)
        assert ".hidden_file" not in action.text
        assert ".hidden_dir" not in action.text
        assert "__pycache__" not in action.text

    @pytest.mark.asyncio
    async def test_empty_directory_says_so(self, paths: PatchbayPaths) -> None:
        action = await _open(paths, paths.patchbay_home / "workspace" / "skills")
        assert "empty" in action.text.lower()

    @pytest.mark.asyncio
    async def test_subdirectory_offers_a_way_back(self, paths: PatchbayPaths) -> None:
        action = await _open(paths, paths.patchbay_home / "workspace")
        back = [b for b in _buttons(action.keyboard) if "Back" in b.text]
        assert len(back) == 1

    @pytest.mark.asyncio
    async def test_back_is_present_at_a_root_too(self, paths: PatchbayPaths) -> None:
        """A button that vanishes at certain depths reads as a broken screen."""
        action = await _open(paths, paths.patchbay_home)
        back = [b for b in _buttons(action.keyboard) if "Back" in b.text]
        assert len(back) == 1

    @pytest.mark.asyncio
    async def test_back_at_a_root_returns_to_the_location_picker(self, paths: PatchbayPaths) -> None:
        action = await _open(paths, paths.patchbay_home)
        back = next(b for b in _buttons(action.keyboard) if "Back" in b.text)
        assert back.callback_data == SF_PREFIX

    @pytest.mark.asyncio
    async def test_back_inside_a_tree_goes_to_the_parent(self, paths: PatchbayPaths) -> None:
        target = paths.patchbay_home / "workspace"
        action = await _open(paths, target)
        back = next(b for b in _buttons(action.keyboard) if "Back" in b.text)
        assert path_tokens.path_for(back.callback_data[len(SF_PREFIX) :]) == target.parent

    @pytest.mark.asyncio
    async def test_navigation_row_is_identical_at_every_depth(self, paths: PatchbayPaths) -> None:
        """Back and Home both show everywhere, including at a root.

        They lead to the same place at a root, which is a cheaper cost than a
        row whose buttons move around depending on how deep you are.
        """
        for target in (paths.patchbay_home, paths.patchbay_home / "workspace"):
            action = await _open(paths, target)
            labels = [b.text for b in _buttons(action.keyboard)]
            assert sum("Back" in x for x in labels) == 1
            assert sum("Home" in x for x in labels) == 1

    @pytest.mark.asyncio
    async def test_nonexistent_directory_falls_back_to_roots(self, paths: PatchbayPaths) -> None:
        action = await _open(paths, paths.patchbay_home / "no-such-dir")
        assert "~/.phoenix-patchbay/" in [b.text for b in _buttons(action.keyboard)]


# -- containment ---------------------------------------------------------------


class TestPathSafety:
    @pytest.mark.asyncio
    async def test_parent_of_root_is_refused(self, paths: PatchbayPaths, tmp_path: Path) -> None:
        action = await _open(paths, paths.patchbay_home.parent)
        assert "~/.phoenix-patchbay/" in [b.text for b in _buttons(action.keyboard)]

    @pytest.mark.asyncio
    async def test_unrelated_absolute_path_is_refused(self, paths: PatchbayPaths) -> None:
        action = await _open(paths, Path("/etc"))
        assert "passwd" not in action.text

    @pytest.mark.asyncio
    async def test_traversal_out_of_root_is_refused(self, paths: PatchbayPaths) -> None:
        escaped = paths.patchbay_home / ".." / ".."
        action = await _open(paths, escaped)
        assert "~/.phoenix-patchbay/" in [b.text for b in _buttons(action.keyboard)]


# -- agent handoff -------------------------------------------------------------


