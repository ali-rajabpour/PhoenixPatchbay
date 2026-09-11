"""Which plugins a conversation's CLI process loads.

Claude Code decides its plugin set once, when the process starts. In an
interactive terminal that makes scoping painful: a plugin enabled mid-session
does nothing until the session is restarted, and one disabled mid-session keeps
working. Patchbay is the opposite case — every turn is a fresh ``claude -p``
process — so a change made here takes effect on the conversation's next message,
with nothing to restart.

Two layers, both optional:

* a persona file at ``<config>/personas/<name>.settings.json``, shipped with the
  installation, which says what that persona normally needs;
* per-conversation overrides, set from ``/plugins``, for the one topic that
  needs a plugin its persona does not.

Only ``enabledPlugins`` is ever taken from those layers. The document handed to
``--settings`` is the real ``settings.json`` with that one key replaced, because
the same file also carries the permission allowlist and the hooks that enforce
the read guard: assembling a settings document from scratch would silently drop
them, and a security regression wearing a token-saving hat is still a security
regression.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from phoenix_patchbay.infra.atomic_io import atomic_text_save
from phoenix_patchbay.personas.catalog import config_dir

logger = logging.getLogger(__name__)

_PLUGINS_KEY = "enabledPlugins"


def _read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError) as exc:
        # Broad on purpose, as in PersonaStore: unreadable settings must degrade
        # to "no scoping" and let the CLI use its own, never block a turn.
        logger.warning("Cannot read settings at %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _plugins_of(data: dict[str, object]) -> dict[str, bool]:
    raw = data.get(_PLUGINS_KEY)
    if not isinstance(raw, dict):
        return {}
    return {str(k): bool(v) for k, v in raw.items()}


def base_settings_path(config: Path | None = None) -> Path:
    """The installation's own ``settings.json``."""
    return (config or config_dir()) / "settings.json"


def persona_settings_path(persona: str, config: Path | None = None) -> Path:
    """Where a persona's plugin scope would live, whether or not it exists."""
    return (config or config_dir()) / "personas" / f"{persona}.settings.json"


def available_plugins(config: Path | None = None) -> dict[str, bool]:
    """Every plugin the installation knows about, with its global default.

    The keyboard is built from this: a plugin absent from ``settings.json`` is
    not installed, and offering it would produce a toggle that does nothing.
    """
    return _plugins_of(_read_json(base_settings_path(config)))


def effective_plugins(
    persona: str,
    overrides: dict[str, bool] | None = None,
    config: Path | None = None,
) -> dict[str, bool]:
    """The plugin set a run would use: global, then persona, then overrides."""
    plugins = available_plugins(config)
    if persona:
        for name, on in _plugins_of(_read_json(persona_settings_path(persona, config))).items():
            if name in plugins:
                plugins[name] = on
    for name, on in (overrides or {}).items():
        if name in plugins:
            plugins[name] = on
    return plugins


def derive_settings(
    persona: str,
    overrides: dict[str, bool] | None = None,
    config: Path | None = None,
) -> str:
    """A settings document for ``--settings``, or ``""`` when none is needed.

    Empty is the common case and the cheap one: when nothing narrows the global
    set, no file is written and no flag is passed, so the CLI reads its own
    configuration exactly as it always has.
    """
    base = _read_json(base_settings_path(config))
    if not base:
        return ""
    wanted = effective_plugins(persona, overrides, config)
    if wanted == _plugins_of(base):
        return ""
    return json.dumps({**base, _PLUGINS_KEY: wanted}, indent=2)


class PluginScopeStore:
    """Per-conversation plugin overrides, keyed by session storage key.

    Only deliberate departures from the persona's scope are stored. A topic that
    never opens ``/plugins`` has no entry at all, so changing what a persona
    ships with reaches every conversation that never disagreed with it.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._overrides: dict[str, dict[str, bool]] = self._load()

    def _load(self) -> dict[str, dict[str, bool]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Cannot read plugin scope store %s: %s", self._path, exc)
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(key): {str(n): bool(v) for n, v in value.items()}
            for key, value in data.items()
            if isinstance(value, dict)
        }

    def _save(self) -> None:
        try:
            atomic_text_save(self._path, json.dumps(self._overrides, indent=2))
        except OSError as exc:
            logger.warning("Cannot write plugin scope store %s: %s", self._path, exc)

    def get(self, storage_key: str) -> dict[str, bool]:
        """This conversation's overrides; empty when it has never set any."""
        return dict(self._overrides.get(storage_key, {}))

    def toggle(
        self,
        storage_key: str,
        plugin: str,
        *,
        persona: str = "",
        config: Path | None = None,
    ) -> bool:
        """Flip *plugin* for this conversation and return its new state.

        An override that agrees with the persona again is dropped rather than
        stored, so the conversation goes back to following its persona.
        """
        current = self._overrides.get(storage_key, {})
        now_on = not effective_plugins(persona, current, config).get(plugin, False)
        inherited = effective_plugins(persona, {}, config).get(plugin, False)
        if now_on == inherited:
            current.pop(plugin, None)
        else:
            current[plugin] = now_on
        if current:
            self._overrides[storage_key] = current
        else:
            self._overrides.pop(storage_key, None)
        self._save()
        return now_on

    def clear(self, storage_key: str) -> None:
        """Drop every override, returning the conversation to its persona."""
        if self._overrides.pop(storage_key, None) is not None:
            self._save()
