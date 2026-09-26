"""``claude setup-token`` driven through a pty, against a stand-in CLI."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from phoenix_patchbay.cli.base import CLIConfig, run_as_wrap
from phoenix_patchbay.cli.claude_accounts import (
    TOKEN_ENV,
    apply_token_to_env,
    read_token,
    save_token,
)
from phoenix_patchbay.cli.claude_login import ClaudeLogin, LoginError, find_token, find_url
from phoenix_patchbay.cli.executor import build_subprocess_env

TOKEN = "sk-ant-oat01-" + "A1b2C3d4_-" * 6

# What the real CLI printed (2.1.283), colour codes and wrapped lines included.
REAL_OUTPUT = (
    "\x1b[>0q\r✢\r\r\n\rBrowser didn't open? Use the url below to sign in\r\r\n\r\r\n"
    "https://claude.com/cai/oauth/authorize?code=true&client_id=9d1c250a\r\r\n"
    "ed-5944d&scope=user%3Ainference&state=EPM0m74\r\r\n\r\r\nPaste code here if prompted> "
)

FAKE_CLI = f"""#!{sys.executable}
import sys
print("Welcome. Opening browser...")
print()
print("https://claude.com/cai/oauth/authorize?code=true&scope=user%3Ainference&state=abc")
print()
print("Paste code here if prompted> ", end="", flush=True)
code = sys.stdin.readline().strip()
if code == "goodcode":
    print()
    print("Your OAuth token (valid for 1 year):")
    print("{TOKEN}")
else:
    print("Invalid code")
"""


@pytest.fixture
def fake_cli(tmp_path: Path) -> str:
    path = tmp_path / "claude"
    path.write_text(FAKE_CLI)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_wrapped_url_is_rejoined_once_a_blank_line_follows_it() -> None:
    from phoenix_patchbay.cli.claude_login import _clean

    url = find_url(_clean(REAL_OUTPUT.encode()))
    assert url == (
        "https://claude.com/cai/oauth/authorize?code=true&client_id=9d1c250aed-5944d"
        "&scope=user%3Ainference&state=EPM0m74"
    )
    # Still arriving: no blank line yet.
    assert find_url("https://claude.com/cai/oauth/authorize?code=tr") is None


def test_token_is_only_returned_once_the_line_is_complete() -> None:
    assert find_token(f"token: {TOKEN}") is None
    assert find_token(f"token: {TOKEN}\n") == TOKEN


async def test_full_dialogue(fake_cli: str) -> None:
    login = ClaudeLogin(cli=fake_cli)
    url = await login.start()
    assert url.startswith("https://claude.com/cai/oauth/authorize")
    assert await login.finish("goodcode") == TOKEN


async def test_wrong_code_is_reported(fake_cli: str) -> None:
    login = ClaudeLogin(cli=fake_cli)
    await login.start()
    with pytest.raises(LoginError, match="not accepted"):
        await login.finish("badcode")


async def test_code_with_spaces_is_refused_before_anything_is_sent(fake_cli: str) -> None:
    login = ClaudeLogin(cli=fake_cli)
    await login.start()
    with pytest.raises(LoginError, match="code"):
        await login.finish("two words")
    login.cancel()


def test_saved_token_is_private_and_reaches_claude_runs(tmp_path: Path) -> None:
    path = save_token(str(tmp_path), TOKEN)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert read_token(str(tmp_path)) == TOKEN
    assert apply_token_to_env({}, str(tmp_path))[TOKEN_ENV] == TOKEN
    assert TOKEN_ENV not in apply_token_to_env({}, str(tmp_path / "none"))

    claude = build_subprocess_env(CLIConfig(provider="claude", claude_account_dir=str(tmp_path)))
    router = build_subprocess_env(CLIConfig(provider="9router", claude_account_dir=str(tmp_path)))
    assert claude is not None
    assert claude[TOKEN_ENV] == TOKEN
    # 9router authenticates through its own endpoint, never with this token.
    assert router is not None
    assert router.get(TOKEN_ENV) != TOKEN


def test_token_reaches_the_account_the_cli_is_dropped_to() -> None:
    env = {"PATH": "/usr/bin", TOKEN_ENV: TOKEN}
    cmd = run_as_wrap(["claude", "-p"], CLIConfig(run_as_user="consult"), env)
    assert f"{TOKEN_ENV}={TOKEN}" in cmd
    assert cmd[:4] == ["sudo", "-n", "-u", "consult"]
    assert os.name == "posix"
