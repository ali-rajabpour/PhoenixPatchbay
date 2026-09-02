"""Tests for cli/factory.py: create_cli backend selection."""

from __future__ import annotations

from unittest.mock import patch

from phoenix_patchbay.cli.base import CLIConfig
from phoenix_patchbay.cli.claude_provider import ClaudeCodeCLI
from phoenix_patchbay.cli.codex_provider import CodexCLI
from phoenix_patchbay.cli.factory import create_cli
from phoenix_patchbay.cli.gemini_provider import GeminiCLI


def test_create_cli_returns_claude_by_default() -> None:
    cli = create_cli(CLIConfig(provider="claude"))
    assert isinstance(cli, ClaudeCodeCLI)


def test_create_cli_returns_codex() -> None:
    cli = create_cli(CLIConfig(provider="codex"))
    assert isinstance(cli, CodexCLI)


def test_create_cli_returns_gemini() -> None:
    with (
        patch("phoenix_patchbay.cli.gemini_provider.find_gemini_cli", return_value="/usr/bin/gemini"),
        patch("phoenix_patchbay.cli.gemini_provider.find_gemini_cli_js", return_value=None),
    ):
        cli = create_cli(CLIConfig(provider="gemini"))
    assert isinstance(cli, GeminiCLI)


def test_create_cli_unknown_provider_returns_claude() -> None:
    cli = create_cli(CLIConfig(provider="unknown"))
    assert isinstance(cli, ClaudeCodeCLI)
