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
    monkeypatch.setenv("NINEROUTER_MODELS", "cc/claude-sonnet-4-5, premium-coding")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.json").write_text('{"ninerouter_api_key": "sk-test"}')

    assert ModelRegistry.provider_for("9router/cc/claude-sonnet-4-5") == "9router"
    assert ninerouter.is_configured()
    assert ninerouter.list_models() == (
        ["9router/premium-coding"],
        ["9router/cc/claude-sonnet-4-5"],
    )

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


async def test_settings_key_is_checked_and_is_the_only_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The /settings key is verified against the router; an environment key is ignored."""
    from aiohttp import web

    async def models(request: web.Request) -> web.Response:
        if request.headers.get("Authorization") != "Bearer sk-good":
            return web.json_response({}, status=401)
        return web.json_response({"data": [{"id": "cc/claude-sonnet-4-5"}, {"id": "premium"}]})

    app = web.Application()
    app.router.add_get("/v1/models", models)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    try:
        monkeypatch.setenv("PATCHBAY_HOME", str(tmp_path))
        monkeypatch.setenv("NINEROUTER_BASE_URL", f"http://127.0.0.1:{port}")
        monkeypatch.setenv("NINEROUTER_API_KEY", "sk-env")

        assert (await ninerouter.verify_api_key("sk-good")).detail == "2"
        assert not (await ninerouter.verify_api_key("sk-bad")).ok
        assert ninerouter.settings()["NINEROUTER_API_KEY"] == ""

        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "config.json").write_text('{"ninerouter_api_key": "sk-good"}')
        assert ninerouter.settings()["NINEROUTER_API_KEY"] == "sk-good"
    finally:
        await runner.cleanup()
