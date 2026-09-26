"""Sign the Claude CLI in from a chat, with ``claude setup-token``.

The CLI only offers a browser flow: it prints a URL, waits for the code the
sign-in page shows, and then prints a long-lived (one year) token. A bot has no
terminal, so this drives that dialogue through a pseudo-terminal and hands the
two human steps (open the URL, paste the code) to whoever is in the chat.

The token is what makes one login enough for every topic: it goes to the CLI in
an environment variable, so the CLI never refreshes or rewrites a credential
file, and a topic run as another unix account can use it without being able to
read the bot's own files.

POSIX only. ``pty`` does not exist on Windows.
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import logging
import os
import pty
import re
import select
import shutil
import signal
import struct
import termios
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

#: Long enough that the CLI does not wrap the URL or the token across lines.
_TTY_COLUMNS = 500
_URL_TIMEOUT = 45.0
_TOKEN_TIMEOUT = 60.0

_ANSI = re.compile(r"\x1b\[[0-9;?<>=]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[78=>]")
_URL_START = re.compile(r"https://claude\.(?:com|ai)/")
_TOKEN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")


class LoginError(Exception):
    """The sign-in could not be completed. The message is safe to show the user."""


def _clean(raw: bytes) -> str:
    return _ANSI.sub("", raw.decode(errors="replace")).replace("\r", "")


def find_url(text: str) -> str | None:
    """The sign-in URL in the CLI's output, or None until it is complete.

    The CLI wraps the URL at the terminal width, so it is the text up to the
    next blank line with the line breaks taken out. A blank line after it is
    what says it has all arrived.
    """
    match = _URL_START.search(text)
    if match is None:
        return None
    block, sep, _ = text[match.start() :].partition("\n\n")
    if not sep:
        return None
    return "".join(block.split())


def find_token(text: str) -> str | None:
    """The token in the CLI's output, or None until it has printed one."""
    match = _TOKEN.search(text)
    if match and match.end() < len(text):
        return match.group(0)
    return None


class ClaudeLogin:
    """One ``claude setup-token`` dialogue: :meth:`start`, then :meth:`finish`."""

    def __init__(self, cli: str | None = None, env: dict[str, str] | None = None) -> None:
        self._cli = cli or shutil.which("claude") or "claude"
        self._env = dict(os.environ if env is None else env)
        # A token already in the environment would make the CLI skip sign-in.
        self._env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        self._pid = 0
        self._fd = -1
        self._buf = b""

    async def start(self) -> str:
        """Launch the CLI and return the URL the user has to open."""
        if self._pid:
            msg = "A sign-in is already running."
            raise LoginError(msg)
        self._spawn()
        url = await self._wait(find_url, _URL_TIMEOUT)
        if url is None:
            self.cancel()
            msg = "The Claude CLI did not print a sign-in link. Is it installed and up to date?"
            raise LoginError(msg)
        return url

    async def finish(self, code: str) -> str:
        """Give the CLI the code from the sign-in page; return the token it prints."""
        code = code.strip()
        if not code or any(c.isspace() for c in code):
            msg = "That does not look like a code. Paste only the code the sign-in page shows."
            raise LoginError(msg)
        if not self._pid:
            msg = "No sign-in is running. Start again with /login claude."
            raise LoginError(msg)
        self._buf = b""
        os.write(self._fd, code.encode() + b"\r")
        token = await self._wait(find_token, _TOKEN_TIMEOUT)
        self.cancel()
        if token is None:
            msg = "The code was not accepted. Start again with /login claude."
            raise LoginError(msg)
        return token

    def cancel(self) -> None:
        """Stop the CLI and release the terminal. Safe to call twice."""
        pid, fd = self._pid, self._fd
        self._pid, self._fd = 0, -1
        if pid:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        # Close the terminal before waiting: on macOS a process cannot finish
        # exiting while its unread output is still queued on the master side.
        if fd >= 0:
            with contextlib.suppress(OSError):
                os.close(fd)
        if pid:
            # Bounded, so a stuck child can never hang the bot.
            for _ in range(40):
                with contextlib.suppress(ChildProcessError):
                    if os.waitpid(pid, os.WNOHANG)[0] == 0:
                        time.sleep(0.05)
                        continue
                break

    def _spawn(self) -> None:
        pid, fd = pty.fork()
        if pid == 0:  # child: size the terminal before the CLI reads it
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", 50, _TTY_COLUMNS, 0, 0))
            os.execvpe(self._cli, [self._cli, "setup-token"], self._env)  # noqa: S606
        self._pid, self._fd = pid, fd

    async def _wait(self, finder: Callable[[str], str | None], seconds: float) -> str | None:
        """Read the terminal until *finder* matches, the CLI exits, or time is up."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            found = finder(_clean(self._buf))
            if found:
                return found
            chunk = await asyncio.to_thread(self._read_some)
            if chunk is None:
                # The CLI exited; one last look at what it printed.
                return finder(_clean(self._buf) + "\n")
            self._buf += chunk
        return None

    def _read_some(self) -> bytes | None:
        """Up to 0.5 s of output, ``b""`` for none yet, None once the CLI is gone."""
        ready, _, _ = select.select([self._fd], [], [], 0.5)
        if not ready:
            return b""
        try:
            data = os.read(self._fd, 4096)
        except OSError:
            return None
        return data or None
