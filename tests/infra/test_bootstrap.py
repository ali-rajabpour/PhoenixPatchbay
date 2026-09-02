"""A container start answers the wizard's questions from the environment.

The wizard needs a TTY. A container has none, so before this existed the first
run printed a banner, said "Setup cancelled", exited, and restart-looped — a
missing answer that reads like a crash.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phoenix_patchbay.infra.bootstrap import config_from_env, ensure_config


def test_a_token_and_a_user_are_enough(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    target = tmp_path / "config" / "config.json"

    assert ensure_config(target) is True
    assert target.exists()


def test_the_token_file_is_not_world_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It holds a bot token; anyone who reads it owns the bot."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    target = tmp_path / "config.json"

    ensure_config(target)

    assert target.stat().st_mode & 0o077 == 0


def test_an_empty_allowlist_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bot with no allowlist answers whoever finds it — never start that."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "")
    target = tmp_path / "config.json"

    with pytest.raises(SystemExit):
        ensure_config(target)

    assert not target.exists()


def test_a_malformed_id_does_not_empty_the_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42, oops, 43")

    config = config_from_env()

    assert config is not None
    assert config["allowed_user_ids"] == [42, 43]


def test_existing_config_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operator's edited config outranks whatever the environment still says."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    target = tmp_path / "config.json"
    target.write_text('{"telegram_bot_token": "real"}', encoding="utf-8")

    assert ensure_config(target) is False
    assert "real" in target.read_text(encoding="utf-8")


def test_no_token_means_no_opinion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A local install without env vars still gets the interactive wizard."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    target = tmp_path / "config.json"

    assert ensure_config(target) is False
    assert not target.exists()


def test_project_roots_can_be_named_or_bare(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "42")
    monkeypatch.setenv("PATCHBAY_PROJECT_ROOTS", "site=/srv/www, /home/patchbay/IT")

    config = config_from_env()

    assert config is not None
    assert config["project_roots"] == {"site": "/srv/www", "IT": "/home/patchbay/IT"}
