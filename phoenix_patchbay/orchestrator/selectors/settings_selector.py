"""Settings you can change from the chat, without touching the host.

The alternative was an SSH session as root on the machine the bot runs on, to
edit one field in a JSON file. That is a worse trade than it looks: it puts a
person on a production host to change a preference, and the reason they are
root is unrelated to the thing they came to do.

What this costs instead is that a secret typed here crosses Telegram. The
message is deleted the moment it is read and the value is never echoed back in
full — but deletion is best effort, and nothing can unsend what was already
delivered. That is an acceptable trade for a free key that only writes
handoffs. It would not be for a credential that can spend money or reach a
database, and no such setting belongs on this screen.

Entries are a list rather than a screen each, so the next setting is a row here
and nothing new to navigate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from phoenix_patchbay.i18n import t
from phoenix_patchbay.orchestrator.selectors.models import Button, ButtonGrid, SelectorResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from phoenix_patchbay.config import AgentConfig

logger = logging.getLogger(__name__)

SET_PREFIX = "set:"
#: One row of the list, opened.
SET_OPEN = "set:o:"
#: Start typing a new value.
SET_EDIT = "set:e:"
#: Clear it.
SET_CLEAR = "set:c:"
#: Back to the list.
SET_ROOT = "set:root"

#: Config values meaning "unset". The example config ships the string "null".
NULLISH = frozenset({"", "null", "none", "-"})


def is_settings_callback(data: str) -> bool:
    return data.startswith(SET_PREFIX)


@dataclass(frozen=True, slots=True)
class Setting:
    """One configurable value: how to read it, check it, and describe it."""

    key: str
    field: str
    validate: Callable[[str], str | None]
    """Returns a translation key for the refusal, or None when the value is fine."""


def _validate_gemini_key(value: str) -> str | None:
    """Reject what is obviously not a Google API key, before it is stored.

    Not authentication — only the API can say whether a key works. This catches
    the paste that went wrong: a URL, a whole curl command, half a key.
    """
    candidate = value.strip()
    if not candidate:
        return "settings.err_empty"
    if any(c.isspace() for c in candidate):
        return "settings.err_spaces"
    if not candidate.startswith("AIza"):
        return "settings.err_shape"
    if len(candidate) < 35:
        return "settings.err_short"
    return None


SETTINGS: tuple[Setting, ...] = (
    Setting(key="gemini", field="gemini_api_key", validate=_validate_gemini_key),
)


def setting_for(key: str) -> Setting | None:
    return next((s for s in SETTINGS if s.key == key), None)


def current_value(config: AgentConfig, setting: Setting) -> str:
    """The stored value, or "" when it is unset in any of its spellings."""
    raw = getattr(config, setting.field, None)
    text = (raw or "").strip() if isinstance(raw, str) else ""
    return "" if text.lower() in NULLISH else text


def mask(value: str) -> str:
    """Enough to recognise a key, never enough to use one.

    Head and tail because that is how a person checks they pasted the right one
    — and four leading characters of a Google key are the same for everybody.
    """
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * 8}{value[-3:]}"


def settings_root(config: AgentConfig) -> SelectorResponse:
    """The list. Each row carries its own state, so the list is the answer."""
    rows = []
    unset = []
    for setting in SETTINGS:
        is_set = bool(current_value(config, setting))
        if not is_set:
            unset.append(setting.key)
        mark = t("settings.state_set") if is_set else t("settings.state_unset")
        rows.append(
            [
                Button(
                    text=f"{t(f'settings.item_{setting.key}')}   {mark}",
                    callback_data=f"{SET_OPEN}{setting.key}",
                )
            ]
        )

    lines = [t("settings.header")]
    # A warning with no consequence attached is noise. Say what it costs.
    for key in unset:
        lines += ["", t(f"settings.consequence_{key}")]
    return SelectorResponse(text="\n".join(lines), buttons=ButtonGrid(rows=rows))


def setting_detail(config: AgentConfig, setting: Setting, notice: str = "") -> SelectorResponse:
    """One setting: what it is for, what is stored, and what can be done."""
    value = current_value(config, setting)
    state = t("settings.state_set") if value else t("settings.state_unset")

    lines = [f"{t(f'settings.item_{setting.key}')}   {state}"]
    if value:
        lines += ["", f"`{mask(value)}`"]
    lines += ["", t(f"settings.about_{setting.key}")]
    if notice:
        lines += ["", notice]

    actions = [
        Button(
            text=t("settings.btn_replace") if value else t("settings.btn_set"),
            callback_data=f"{SET_EDIT}{setting.key}",
        )
    ]
    if value:
        actions.append(
            Button(text=t("settings.btn_clear"), callback_data=f"{SET_CLEAR}{setting.key}")
        )
    back = [Button(text=t("settings.btn_list"), callback_data=SET_ROOT)]
    return SelectorResponse(text="\n".join(lines), buttons=ButtonGrid(rows=[actions, back]))


def ask_for_value(setting: Setting, refusal: str = "") -> SelectorResponse:
    """Prompt for the value, with a way out that is not "send something"."""
    lines = []
    if refusal:
        lines += [t(refusal), ""]
    lines.append(t(f"settings.ask_{setting.key}"))
    lines += ["", t("settings.ask_privacy")]
    cancel = [Button(text=t("settings.btn_cancel"), callback_data=f"{SET_OPEN}{setting.key}")]
    return SelectorResponse(text="\n".join(lines), buttons=ButtonGrid(rows=[cancel]))


def parse_callback(data: str) -> tuple[str, str] | None:
    """Split ``set:<action>:<key>`` into ``(action, key)``. None for the root."""
    for prefix, action in ((SET_OPEN, "open"), (SET_EDIT, "edit"), (SET_CLEAR, "clear")):
        if data.startswith(prefix):
            return action, data[len(prefix) :]
    return None
