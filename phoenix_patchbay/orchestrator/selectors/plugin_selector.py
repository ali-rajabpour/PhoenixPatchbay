"""Plugin picker for ``/plugins``.

One toggle per installed plugin. Unlike the persona picker there is no gate and
no "ask on a new conversation": a conversation that never opens this menu runs
whatever its persona ships with, which is the point of scoping personas in the
first place.

A tap takes effect on the next message, because that message is a new CLI
process. Nothing has to be restarted and nothing keeps running after it is
switched off — the awkward part of doing this in an interactive terminal.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from phoenix_patchbay.i18n import t
from phoenix_patchbay.orchestrator.selectors.models import Button, ButtonGrid, SelectorResponse
from phoenix_patchbay.personas.plugin_scope import available_plugins, effective_plugins

if TYPE_CHECKING:
    from phoenix_patchbay.orchestrator.core import Orchestrator
    from phoenix_patchbay.session.key import SessionKey

logger = logging.getLogger(__name__)

PLG_PREFIX = "plg:"

#: Plugins are addressed by index: names like ``ali-design@ali`` are long, and
#: Telegram caps callback_data at 64 bytes.
_BUTTONS_PER_ROW = 2


def is_plugin_selector_callback(data: str) -> bool:
    """Return True if *data* belongs to the plugin picker."""
    return data.startswith(PLG_PREFIX)


def plugin_names() -> list[str]:
    """Installed plugins, in a stable order the callback index can rely on."""
    return sorted(available_plugins())


def _label(name: str) -> str:
    """``caveman@caveman`` reads as ``caveman``; the marketplace adds nothing."""
    return name.split("@", 1)[0]


def plugin_selector(orch: Orchestrator, key: SessionKey) -> SelectorResponse:
    """Build the toggle keyboard for this conversation."""
    names = plugin_names()
    if not names:
        return SelectorResponse(text=t("plugins.none_installed"), buttons=ButtonGrid(rows=[]))

    persona = orch.personas.get(key.storage_key) or ""
    overrides = orch.plugin_scope.get(key.storage_key)
    active = effective_plugins(persona, overrides)

    lines = [t("plugins.header"), ""]
    lines.append(t("plugins.persona_line", persona=persona) if persona else t("plugins.no_persona"))
    lines.append("")
    for name in names:
        mark = "✅" if active.get(name) else "⬜"
        star = " •" if name in overrides else ""
        lines.append(f"{mark} `{_label(name)}`{star}")
    if overrides:
        lines += ["", t("plugins.override_note")]

    buttons = [
        Button(
            text=f"{'✅' if active.get(name) else '⬜'} {_label(name)}",
            callback_data=f"{PLG_PREFIX}{i}",
        )
        for i, name in enumerate(names)
    ]
    rows = [buttons[i : i + _BUTTONS_PER_ROW] for i in range(0, len(buttons), _BUTTONS_PER_ROW)]
    return SelectorResponse(text="\n".join(lines), buttons=ButtonGrid(rows=rows))


def resolve_choice(index: int) -> str | None:
    """Map a callback index to a plugin name."""
    names = plugin_names()
    if 0 <= index < len(names):
        return names[index]
    return None


def parse_callback(data: str) -> int | None:
    """Extract the index from ``plg:<index>``."""
    try:
        return int(data[len(PLG_PREFIX) :])
    except ValueError:
        logger.debug("Bad plugin callback: %r", data)
        return None
