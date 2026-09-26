"""The personas shipped in deploy/seed must load, and must stay generic."""

from __future__ import annotations

import json
import re
from pathlib import Path

from phoenix_patchbay.personas.catalog import load_personas

SEED = Path(__file__).resolve().parents[2] / "deploy" / "seed"
# Anything that ties a persona to one person's machine or private plugins.
PRIVATE = re.compile(r"\bali\b|ali-|salam|glitchtip|cloudflare|21st|/Users/|/home/|@ali", re.IGNORECASE)


def test_all_five_personas_load_in_picker_order() -> None:
    names = [p.name for p in load_personas(SEED)]
    assert names == ["default", "coder", "web-designer", "scout", "researcher"]


def test_seeded_files_carry_nothing_private() -> None:
    files = [*SEED.glob("agents/*.md"), *SEED.glob("personas/*.json")]
    assert files
    for file in files:
        assert not PRIVATE.search(file.read_text(encoding="utf-8")), file.name


def test_plugin_scopes_only_name_plugins_the_image_installs() -> None:
    installed = set(json.loads((SEED / "claude-settings.json").read_text())["enabledPlugins"])
    for file in SEED.glob("personas/*.settings.json"):
        assert set(json.loads(file.read_text())["enabledPlugins"]) <= installed, file.name
