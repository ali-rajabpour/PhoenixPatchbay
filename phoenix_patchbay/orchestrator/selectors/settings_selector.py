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

from phoenix_patchbay.cli.gemini_verify import VerifyResult, verify_gemini_key
from phoenix_patchbay.i18n import t
from phoenix_patchbay.orchestrator.selectors.models import Button, ButtonGrid, SelectorResponse

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from phoenix_patchbay.config import AgentConfig

logger = logging.getLogger(__name__)

SET_PREFIX = "set:"
#: One row of the list, opened.
SET_OPEN = "set:o:"
#: Start typing a new value.
SET_EDIT = "set:e:"
#: Clear it.
SET_CLEAR = "set:c:"
#: Re-check a stored value against the service that owns it.
SET_TEST = "set:t:"
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
    verify: Callable[[str], Awaitable[VerifyResult]]
    """Ask the service that owns this value whether it works.

    A live check rather than a pattern: a regex can only say the value looks
    plausible, which is the one thing nobody needs to be told. It rejects a
    valid key whose format changed, accepts a revoked one, and cannot see the
    typo it is supposedly guarding against.
    """


SETTINGS: tuple[Setting, ...] = (
    Setting(key="gemini", field="gemini_api_key", verify=verify_gemini_key),
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
        # Keys get revoked and quotas run out, so "it worked when you typed it"
        # stops being true without anything on this screen changing.
        actions.append(
            Button(text=t("settings.btn_test"), callback_data=f"{SET_TEST}{setting.key}")
        )
        actions.append(
            Button(text=t("settings.btn_clear"), callback_data=f"{SET_CLEAR}{setting.key}")
        )
    back = [Button(text=t("settings.btn_list"), callback_data=SET_ROOT)]
    return SelectorResponse(text="\n".join(lines), buttons=ButtonGrid(rows=[actions, back]))


def checking_screen(setting: Setting) -> SelectorResponse:
    """Shown while the service is asked. A live check takes a visible moment.

    No buttons: every action here would race the check that is already running.
    """
    return SelectorResponse(
        text=f"{t(f'settings.item_{setting.key}')}\n\n{t('settings.checking')}",
        buttons=None,
    )


def verdict_notice(result: VerifyResult) -> str:
    """One line saying what the service answered."""
    if result.ok:
        if result.detail:
            return t("settings.verified_with_models", count=result.detail)
        return t("settings.verified")
    return t(result.reason or "settings.err_rejected")


def ask_for_value(setting: Setting, notice: str = "") -> SelectorResponse:
    """Prompt for the value, with a way out that is not "send something".

    *notice* is rendered text, not a translation key: it comes from
    :func:`verdict_notice`, which has already turned the service's answer into
    a sentence. Passing a key here would double-translate it.
    """
    lines = []
    if notice:
        lines += [notice, ""]
    lines.append(t(f"settings.ask_{setting.key}"))
    lines += ["", t("settings.ask_privacy")]
    cancel = [Button(text=t("settings.btn_cancel"), callback_data=f"{SET_OPEN}{setting.key}")]
    return SelectorResponse(text="\n".join(lines), buttons=ButtonGrid(rows=[cancel]))


def parse_callback(data: str) -> tuple[str, str] | None:
    """Split ``set:<action>:<key>`` into ``(action, key)``. None for the root."""
    for prefix, action in (
        (SET_OPEN, "open"),
        (SET_EDIT, "edit"),
        (SET_CLEAR, "clear"),
        (SET_TEST, "test"),
    ):
        if data.startswith(prefix):
            return action, data[len(prefix) :]
    return None
