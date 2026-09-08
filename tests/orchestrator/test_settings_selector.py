"""The settings screens, and the masking that keeps a secret off them."""

from __future__ import annotations

import pytest

from phoenix_patchbay.cli.gemini_verify import VerifyResult
from phoenix_patchbay.config import AgentConfig
from phoenix_patchbay.i18n import init
from phoenix_patchbay.orchestrator.selectors.settings_selector import (
    SETTINGS,
    ask_for_value,
    checking_screen,
    current_value,
    is_settings_callback,
    mask,
    parse_callback,
    setting_detail,
    setting_for,
    settings_root,
    verdict_notice,
)

KEY = "AIzaSyDUMMYdummyDUMMYdummyDUMMYdummy1234"


@pytest.fixture(autouse=True)
def _english() -> None:
    init("en")


def _config(**kw: object) -> AgentConfig:
    return AgentConfig(allowed_user_ids=[1], **kw)


class TestMasking:
    def test_a_key_is_never_shown_in_full(self) -> None:
        masked = mask(KEY)
        assert KEY not in masked
        assert masked.startswith("AIza")
        assert masked.endswith(KEY[-3:])

    def test_a_short_value_gives_nothing_away(self) -> None:
        """Head-and-tail of a short string is most of the string."""
        assert mask("abcd1234") == "•" * 8

    def test_the_detail_screen_shows_only_the_mask(self) -> None:
        resp = setting_detail(_config(gemini_api_key=KEY), setting_for("gemini"))
        assert KEY not in resp.text
        assert mask(KEY) in resp.text


class TestState:
    def test_the_placeholder_counts_as_unset(self) -> None:
        """The example config ships the string "null", not an empty one."""
        assert current_value(_config(gemini_api_key="null"), setting_for("gemini")) == ""

    def test_whitespace_counts_as_unset(self) -> None:
        assert current_value(_config(gemini_api_key="   "), setting_for("gemini")) == ""

    def test_the_list_says_which_way_round_it_is(self) -> None:
        unset = settings_root(_config(gemini_api_key="null"))
        assert "⚠️" in unset.buttons.rows[0][0].text
        was_set = settings_root(_config(gemini_api_key=KEY))
        assert "✅" in was_set.buttons.rows[0][0].text

    def test_an_unset_value_says_what_it_costs(self) -> None:
        """A warning with no consequence attached is decoration."""
        assert "$0.17" in settings_root(_config(gemini_api_key="null")).text
        assert "$0.17" not in settings_root(_config(gemini_api_key=KEY)).text

    def test_a_stored_value_can_be_re_tested(self) -> None:
        """Keys get revoked and quotas run out without this screen changing."""
        buttons = setting_detail(_config(gemini_api_key=KEY), setting_for("gemini")).buttons
        labels = [b.text for row in buttons.rows for b in row]
        assert any("Test" in label for label in labels)

        buttons = setting_detail(_config(gemini_api_key="null"), setting_for("gemini")).buttons
        labels = [b.text for row in buttons.rows for b in row]
        assert not any("Test" in label for label in labels)

    def test_remove_is_offered_only_when_there_is_something_to_remove(self) -> None:
        buttons = setting_detail(_config(gemini_api_key=KEY), setting_for("gemini")).buttons
        labels = [b.text for row in buttons.rows for b in row]
        assert any("Remove" in label for label in labels)

        buttons = setting_detail(_config(gemini_api_key="null"), setting_for("gemini")).buttons
        labels = [b.text for row in buttons.rows for b in row]
        assert not any("Remove" in label for label in labels)


class TestVerdict:
    """What the screen says after the service has answered."""

    def test_success_names_the_evidence(self) -> None:
        assert "2" in verdict_notice(VerifyResult(ok=True, detail="2"))

    def test_success_without_a_count_still_reads_as_working(self) -> None:
        assert "✅" in verdict_notice(VerifyResult(ok=True))

    def test_a_refusal_tells_the_user_what_to_do(self) -> None:
        text = verdict_notice(VerifyResult(ok=False, reason="settings.err_rejected"))
        assert "AI Studio" in text

    def test_a_spent_quota_does_not_read_as_a_bad_key(self) -> None:
        text = verdict_notice(VerifyResult(ok=False, reason="settings.err_quota"))
        assert "valid" in text.lower()

    def test_an_unknown_failure_falls_back_to_refused(self) -> None:
        assert verdict_notice(VerifyResult(ok=False)) != ""


class TestCheckingScreen:
    def test_it_offers_no_buttons(self) -> None:
        """Every action here would race the check that is already running."""
        assert checking_screen(setting_for("gemini")).buttons is None

    def test_it_says_what_is_happening(self) -> None:
        assert "Checking" in checking_screen(setting_for("gemini")).text



class TestPrompt:
    def test_the_question_warns_where_the_message_goes(self) -> None:
        """The user is about to paste a secret into a chat; say so first."""
        text = ask_for_value(setting_for("gemini")).text
        assert "deleted" in text
        assert "Telegram" in text

    def test_the_services_answer_is_shown_above_the_question(self) -> None:
        """Rendered text, not a key: verdict_notice has already translated it."""
        notice = verdict_notice(VerifyResult(ok=False, reason="settings.err_rejected"))
        text = ask_for_value(setting_for("gemini"), notice).text

        assert "❌" in text
        assert text.index("❌") < text.index("Send the key")

    def test_the_question_can_be_left(self) -> None:
        """A screen whose only exit is sending something is a trap."""
        buttons = ask_for_value(setting_for("gemini")).buttons
        assert any("Cancel" in b.text for row in buttons.rows for b in row)


class TestCallbacks:
    def test_only_our_namespace_is_claimed(self) -> None:
        assert is_settings_callback("set:o:gemini")
        assert not is_settings_callback("mnu:3")
        assert not is_settings_callback("cns:1")

    def test_round_trip(self) -> None:
        for setting in SETTINGS:
            for prefix, action in (
                ("set:o:", "open"),
                ("set:e:", "edit"),
                ("set:c:", "clear"),
                ("set:t:", "test"),
            ):
                assert parse_callback(f"{prefix}{setting.key}") == (action, setting.key)

    def test_the_root_is_not_an_action(self) -> None:
        assert parse_callback("set:root") is None

    def test_an_unknown_setting_key_resolves_to_nothing(self) -> None:
        assert setting_for("does-not-exist") is None
