"""Tests for PATCHBAY_TRANSCRIBE_COMMAND env injection on CLI subprocess (#66)."""

from __future__ import annotations

from pathlib import Path

import pytest

from phoenix_patchbay.cli.base import CLIConfig
from phoenix_patchbay.cli.executor import build_subprocess_env


def test_transcribe_env_unset_not_injected(tmp_path: Path) -> None:
    cfg = CLIConfig(working_dir=tmp_path)
    env = build_subprocess_env(cfg)

    assert env is not None
    assert "PATCHBAY_TRANSCRIBE_COMMAND" not in env
    assert "PATCHBAY_VIDEO_TRANSCRIBE_COMMAND" not in env


def test_transcribe_env_set(tmp_path: Path) -> None:
    cfg = CLIConfig(working_dir=tmp_path, transcribe_command="/usr/bin/my-transcribe --fast")
    env = build_subprocess_env(cfg)

    assert env is not None
    assert env["PATCHBAY_TRANSCRIBE_COMMAND"] == "/usr/bin/my-transcribe --fast"
    assert "PATCHBAY_VIDEO_TRANSCRIBE_COMMAND" not in env


def test_video_transcribe_env_set(tmp_path: Path) -> None:
    cfg = CLIConfig(
        working_dir=tmp_path,
        video_transcribe_command="~/.local/bin/vid-transcribe.sh",
    )
    env = build_subprocess_env(cfg)

    assert env is not None
    assert env["PATCHBAY_VIDEO_TRANSCRIBE_COMMAND"] == "~/.local/bin/vid-transcribe.sh"
    assert "PATCHBAY_TRANSCRIBE_COMMAND" not in env


def test_both_transcribe_env_vars_set(tmp_path: Path) -> None:
    cfg = CLIConfig(
        working_dir=tmp_path,
        transcribe_command="a.sh",
        video_transcribe_command="b.sh",
    )
    env = build_subprocess_env(cfg)

    assert env is not None
    assert env["PATCHBAY_TRANSCRIBE_COMMAND"] == "a.sh"
    assert env["PATCHBAY_VIDEO_TRANSCRIBE_COMMAND"] == "b.sh"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
