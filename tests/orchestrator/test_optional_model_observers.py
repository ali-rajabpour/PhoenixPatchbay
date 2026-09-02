"""Tests for optional provider model-cache observers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from phoenix_patchbay.cli.codex_cache import CodexModelCache
from phoenix_patchbay.orchestrator.observers import ObserverManager


def _manager() -> ObserverManager:
    return ObserverManager(MagicMock(), MagicMock())


async def test_skips_observers_for_missing_optional_clis() -> None:
    manager = _manager()

    with (
        patch("phoenix_patchbay.orchestrator.observers.GeminiCacheObserver") as gemini_cls,
        patch("phoenix_patchbay.orchestrator.observers.AntigravityCacheObserver") as agy_cls,
        patch("phoenix_patchbay.orchestrator.observers.GrokCacheObserver") as grok_cls,
        patch("phoenix_patchbay.orchestrator.observers.CodexCacheObserver") as codex_cls,
    ):
        cache = await manager.init_model_caches(
            installed_providers=frozenset({"claude"}),
            on_gemini_refresh=MagicMock(),
            on_antigravity_refresh=MagicMock(),
            on_grok_refresh=MagicMock(),
        )

    gemini_cls.assert_not_called()
    agy_cls.assert_not_called()
    grok_cls.assert_not_called()
    codex_cls.assert_not_called()
    assert manager.gemini_cache_obs is None
    assert manager.antigravity_cache_obs is None
    assert manager.grok_cache_obs is None
    assert manager.codex_cache_obs is None
    assert cache.models == []


async def test_starts_observers_for_installed_optional_clis() -> None:
    manager = _manager()
    gemini_observer = MagicMock()
    gemini_observer.start = AsyncMock()
    agy_observer = MagicMock()
    agy_observer.start = AsyncMock()
    grok_observer = MagicMock()
    grok_observer.start = AsyncMock()
    codex_observer = MagicMock()
    codex_observer.start = AsyncMock()
    codex_observer.get_cache.return_value = CodexModelCache("", [])

    with (
        patch(
            "phoenix_patchbay.orchestrator.observers.GeminiCacheObserver",
            return_value=gemini_observer,
        ),
        patch(
            "phoenix_patchbay.orchestrator.observers.AntigravityCacheObserver",
            return_value=agy_observer,
        ),
        patch("phoenix_patchbay.orchestrator.observers.GrokCacheObserver", return_value=grok_observer),
        patch("phoenix_patchbay.orchestrator.observers.CodexCacheObserver", return_value=codex_observer),
    ):
        await manager.init_model_caches(
            installed_providers=frozenset({"claude", "codex", "gemini", "antigravity", "grok"}),
            on_gemini_refresh=MagicMock(),
            on_antigravity_refresh=MagicMock(),
            on_grok_refresh=MagicMock(),
        )

    gemini_observer.start.assert_awaited_once()
    agy_observer.start.assert_awaited_once()
    grok_observer.start.assert_awaited_once()
    assert manager.gemini_cache_obs is gemini_observer
    assert manager.antigravity_cache_obs is agy_observer
    assert manager.grok_cache_obs is grok_observer
    assert manager.codex_cache_obs is codex_observer
    codex_observer.start.assert_awaited_once()


async def test_installed_but_unauthenticated_provider_still_gets_observer() -> None:
    """INSTALLED (not AUTHENTICATED) is enough — the set is auth-detection based."""
    manager = _manager()
    codex_observer = MagicMock()
    codex_observer.start = AsyncMock()
    codex_observer.get_cache.return_value = CodexModelCache("", [])

    with (
        patch("phoenix_patchbay.orchestrator.observers.GeminiCacheObserver") as gemini_cls,
        patch("phoenix_patchbay.orchestrator.observers.AntigravityCacheObserver") as agy_cls,
        patch("phoenix_patchbay.orchestrator.observers.GrokCacheObserver") as grok_cls,
        patch("phoenix_patchbay.orchestrator.observers.CodexCacheObserver", return_value=codex_observer),
    ):
        await manager.init_model_caches(
            installed_providers=frozenset({"claude", "codex"}),
            on_gemini_refresh=MagicMock(),
            on_antigravity_refresh=MagicMock(),
            on_grok_refresh=MagicMock(),
        )

    gemini_cls.assert_not_called()
    agy_cls.assert_not_called()
    grok_cls.assert_not_called()
    codex_observer.start.assert_awaited_once()
