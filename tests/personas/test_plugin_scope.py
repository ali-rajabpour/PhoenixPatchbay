"""Plugin scoping: persona defaults, per-conversation overrides, and what is safe to drop."""

from __future__ import annotations

import json
from pathlib import Path

from phoenix_patchbay.personas.plugin_scope import (
    PluginScopeStore,
    available_plugins,
    derive_settings,
    effective_plugins,
)

BASE = {
    "model": "opus",
    "permissions": {"allow": ["Bash(rtk ls *)"], "defaultMode": "bypassPermissions"},
    "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"command": "guard"}]}]},
    "enabledPlugins": {"caveman@caveman": True, "ali-design@ali": True, "github@x": False},
}


def _config(tmp_path: Path, persona: dict[str, object] | None = None) -> Path:
    (tmp_path / "settings.json").write_text(json.dumps(BASE), encoding="utf-8")
    if persona is not None:
        personas = tmp_path / "personas"
        personas.mkdir()
        (personas / "coder.settings.json").write_text(json.dumps(persona), encoding="utf-8")
    return tmp_path


def test_available_plugins_lists_the_installation_defaults(tmp_path: Path) -> None:
    assert available_plugins(_config(tmp_path)) == BASE["enabledPlugins"]


def test_a_persona_narrows_the_global_set(tmp_path: Path) -> None:
    config = _config(tmp_path, {"enabledPlugins": {"ali-design@ali": False}})
    assert effective_plugins("coder", config=config)["ali-design@ali"] is False
    assert effective_plugins("coder", config=config)["caveman@caveman"] is True


def test_an_override_beats_the_persona(tmp_path: Path) -> None:
    config = _config(tmp_path, {"enabledPlugins": {"ali-design@ali": False}})
    plugins = effective_plugins("coder", {"ali-design@ali": True}, config=config)
    assert plugins["ali-design@ali"] is True


def test_a_plugin_that_is_not_installed_is_ignored(tmp_path: Path) -> None:
    # A persona file outliving a plugin must not resurrect it as a key the CLI
    # would then be asked to load.
    config = _config(tmp_path, {"enabledPlugins": {"gone@nowhere": True}})
    assert "gone@nowhere" not in effective_plugins("coder", {"also-gone@x": True}, config=config)


def test_derive_keeps_the_permissions_and_hooks_it_did_not_come_to_change(tmp_path: Path) -> None:
    # The whole point of overlaying one key onto the real settings file: a
    # hand-built document would silently drop the read guard.
    config = _config(tmp_path, {"enabledPlugins": {"ali-design@ali": False}})
    derived = json.loads(derive_settings("coder", config=config))
    assert derived["hooks"] == BASE["hooks"]
    assert derived["permissions"] == BASE["permissions"]
    assert derived["model"] == "opus"
    assert derived["enabledPlugins"]["ali-design@ali"] is False


def test_nothing_is_written_when_nothing_narrows(tmp_path: Path) -> None:
    assert derive_settings("", config=_config(tmp_path)) == ""
    config = _config(tmp_path, {"enabledPlugins": {"caveman@caveman": True}})
    assert derive_settings("coder", config=config) == ""


def test_a_missing_persona_file_is_not_an_error(tmp_path: Path) -> None:
    assert derive_settings("nobody", config=_config(tmp_path)) == ""


def test_toggle_flips_then_forgets_when_it_agrees_again(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = PluginScopeStore(tmp_path / "plugin_scope.json")
    assert store.toggle("c1", "caveman@caveman", config=config) is False  # global default was on
    assert store.get("c1") == {"caveman@caveman": False}
    # Back to what it inherits: the override is dropped rather than pinned, so a
    # later change to the persona still reaches this conversation.
    assert store.toggle("c1", "caveman@caveman", config=config) is True
    assert store.get("c1") == {}
    assert derive_settings("", store.get("c1"), config=config) == ""


def test_overrides_are_per_conversation_and_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "plugin_scope.json"
    store = PluginScopeStore(path)
    store.toggle("c1", "caveman@caveman", config=_config(tmp_path))
    assert PluginScopeStore(path).get("c1") == {"caveman@caveman": False}
    assert PluginScopeStore(path).get("c2") == {}


def test_clear_returns_a_conversation_to_its_persona(tmp_path: Path) -> None:
    store = PluginScopeStore(tmp_path / "plugin_scope.json")
    store.toggle("c1", "caveman@caveman", config=_config(tmp_path))
    store.clear("c1")
    assert store.get("c1") == {}
