"""CLI backend factory -- returns the right provider based on config."""

from __future__ import annotations

import logging

from phoenix_patchbay.cli.base import BaseCLI, CLIConfig

logger = logging.getLogger(__name__)


def create_cli(config: CLIConfig) -> BaseCLI:
    """Create a CLI backend instance based on ``config.provider``."""
    logger.debug("CLI factory creating provider=%s", config.provider)
    if config.provider == "gemini":
        from phoenix_patchbay.cli.gemini_provider import GeminiCLI

        return GeminiCLI(config)

    if config.provider == "codex":
        from phoenix_patchbay.cli.codex_provider import CodexCLI

        return CodexCLI(config)

    if config.provider == "antigravity":
        from phoenix_patchbay.cli.antigravity_provider import AntigravityCLI

        return AntigravityCLI(config)

    if config.provider == "grok":
        from phoenix_patchbay.cli.grok_provider import GrokCLI

        return GrokCLI(config)

    from phoenix_patchbay.cli.claude_provider import ClaudeCodeCLI

    return ClaudeCodeCLI(config)
