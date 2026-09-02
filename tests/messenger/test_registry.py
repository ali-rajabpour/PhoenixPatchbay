"""Tests for the transport registry."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from phoenix_patchbay.messenger.registry import create_bot


class TestTransportRegistry:
    def test_unknown_transport_raises(self) -> None:
        config = MagicMock()
        config.transport = "discord"
        config.is_multi_transport = False
        with pytest.raises(ValueError, match=r"Unknown transport.*discord"):
            create_bot(config)

    def test_telegram_transport(self) -> None:
        config = MagicMock()
        config.transport = "telegram"
        config.is_multi_transport = False
        fake_bot = MagicMock()
        with patch("phoenix_patchbay.messenger.telegram.app.TelegramBot", return_value=fake_bot):
            bot = create_bot(config, agent_name="test")
        assert bot is fake_bot

    def test_matrix_transport(self) -> None:
        config = MagicMock()
        config.transport = "matrix"
        config.is_multi_transport = False
        fake_bot = MagicMock()
        with patch("phoenix_patchbay.messenger.matrix.bot.MatrixBot", return_value=fake_bot):
            bot = create_bot(config, agent_name="test")
        assert bot is fake_bot

    def test_slack_transport(self) -> None:
        config = MagicMock()
        config.transport = "slack"
        config.is_multi_transport = False
        fake_bot = MagicMock()
        with patch("phoenix_patchbay.messenger.slack.bot.SlackBot", return_value=fake_bot):
            bot = create_bot(config, agent_name="test")
        assert bot is fake_bot
