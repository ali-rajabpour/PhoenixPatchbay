"""deploy/consult-access.sh must never break a start, whatever the box looks like."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "consult-access.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


def test_script_parses() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0


def test_no_consult_account_is_a_quiet_no_op(tmp_path: Path) -> None:
    # A stub `id` that always fails stands in for an image without the account.
    stub = tmp_path / "id"
    stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(0o755)
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": f"{tmp_path}:/usr/bin:/bin", "HOME": str(tmp_path)},
        timeout=30,
    )
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert proc.stderr == ""
