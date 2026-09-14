"""9router: routing, env wiring and command building."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phoenix_patchbay.cli import ninerouter
from phoenix_patchbay.cli.base import CLIConfig
from phoenix_patchbay.cli.claude_provider import ClaudeCodeCLI
from phoenix_patchbay.config import ModelRegistry

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_ninerouter_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATCHBAY_HOME", str(tmp_path))
    monkeypatch.setenv("NINEROUTER_BASE_URL", "http://router.mesh:20128/v1/")
    monkeypatch.setenv("NINEROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("NINEROUTER_MODELS", "cc/claude-sonnet-4-5, premium-coding")

    assert ModelRegistry.provider_for("9router/cc/claude-sonnet-4-5") == "9router"
    assert ninerouter.is_configured()
    assert ninerouter.list_models() == ["9router/cc/claude-sonnet-4-5", "9router/premium-coding"]

    env = {"ANTHROPIC_API_KEY": "real-key"}
    ninerouter.apply_to_env(env)
    assert env == {
        "ANTHROPIC_BASE_URL": "http://router.mesh:20128",
        "ANTHROPIC_AUTH_TOKEN": "sk-test",
    }

    monkeypatch.setattr(ClaudeCodeCLI, "_find_cli", staticmethod(lambda: "claude"))
    cli = ClaudeCodeCLI(
        CLIConfig(
            provider="9router",
            working_dir=str(tmp_path),
            model="9router/cc/claude-sonnet-4-5",
            reasoning_effort="high",
        )
    )
    cmd = cli._build_command("hi")
    assert cmd[cmd.index("--model") + 1] == "cc/claude-sonnet-4-5"
    assert "--effort" not in cmd
