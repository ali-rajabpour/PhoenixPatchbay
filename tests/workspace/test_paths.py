"""Tests for PatchbayPaths and resolve_paths."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from phoenix_patchbay.workspace.paths import PatchbayPaths, resolve_paths


def test_workspace_property() -> None:
    paths = PatchbayPaths(
        patchbay_home=Path("/home/test/.phoenix-patchbay"),
        home_defaults=Path("/opt/patchbay/workspace"),
        framework_root=Path("/opt/patchbay"),
    )
    assert paths.workspace == Path("/home/test/.phoenix-patchbay/workspace")


def test_config_path() -> None:
    paths = PatchbayPaths(
        patchbay_home=Path("/home/test/.phoenix-patchbay"),
        home_defaults=Path("/opt/patchbay/workspace"),
        framework_root=Path("/opt/patchbay"),
    )
    assert paths.config_path == Path("/home/test/.phoenix-patchbay/config/config.json")


def test_sessions_path() -> None:
    paths = PatchbayPaths(
        patchbay_home=Path("/home/test/.phoenix-patchbay"),
        home_defaults=Path("/opt/patchbay/workspace"),
        framework_root=Path("/opt/patchbay"),
    )
    assert paths.sessions_path == Path("/home/test/.phoenix-patchbay/sessions.json")


def test_logs_dir() -> None:
    paths = PatchbayPaths(
        patchbay_home=Path("/home/test/.phoenix-patchbay"),
        home_defaults=Path("/opt/patchbay/workspace"),
        framework_root=Path("/opt/patchbay"),
    )
    assert paths.logs_dir == Path("/home/test/.phoenix-patchbay/logs")


def test_home_defaults() -> None:
    paths = PatchbayPaths(
        patchbay_home=Path("/x"),
        home_defaults=Path("/opt/patchbay/workspace"),
        framework_root=Path("/opt/patchbay"),
    )
    assert paths.home_defaults == Path("/opt/patchbay/workspace")


def test_resolve_paths_explicit() -> None:
    paths = resolve_paths(patchbay_home="/tmp/test_home", framework_root="/tmp/test_fw")
    assert paths.patchbay_home == Path("/tmp/test_home").resolve()
    assert paths.framework_root == Path("/tmp/test_fw").resolve()


def test_resolve_paths_env_vars() -> None:
    with patch.dict(
        os.environ, {"PATCHBAY_HOME": "/tmp/env_home", "PATCHBAY_FRAMEWORK_ROOT": "/tmp/env_fw"}
    ):
        paths = resolve_paths()
        assert paths.patchbay_home == Path("/tmp/env_home").resolve()
        assert paths.framework_root == Path("/tmp/env_fw").resolve()


def test_resolve_paths_defaults() -> None:
    with patch.dict(os.environ, {}, clear=True):
        env_clean = {
            k: v for k, v in os.environ.items() if k not in ("PATCHBAY_HOME", "PATCHBAY_FRAMEWORK_ROOT")
        }
        with patch.dict(os.environ, env_clean, clear=True):
            paths = resolve_paths()
            assert paths.patchbay_home == (Path.home() / ".phoenix-patchbay").resolve()
