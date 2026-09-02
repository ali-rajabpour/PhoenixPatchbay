"""Central path resolution for the workspace layout.

This module is the SINGLE SOURCE OF TRUTH for all paths in the framework.
Every path the framework needs is either a field or property of ``PatchbayPaths``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# phoenix_patchbay/workspace/paths.py -> phoenix_patchbay/workspace -> phoenix_patchbay
_PKG_DIR = Path(__file__).resolve().parent.parent


def _default_home_defaults() -> Path:
    return _PKG_DIR / "_home_defaults"


def _default_framework_root() -> Path:
    return _PKG_DIR.parent


#: Unix account the Consult topic's CLI is dropped to. Defined here because
#: both the transport (which creates the directory) and the CLI layer (which
#: drops to the account) need it, and neither should import the other.
CONSULT_USER = "consult"


@dataclass(frozen=True)
class PatchbayPaths:
    """Resolved, immutable paths for the workspace layout.

    All framework paths are derived from three roots:

    - ``patchbay_home``:    User data directory (default ``~/.phoenix-patchbay``).
    - ``home_defaults``:  Bundled template that mirrors ``patchbay_home`` (package-internal).
    - ``framework_root``: Repository root (for Dockerfile, config.example.json).
    """

    patchbay_home: Path
    home_defaults: Path = field(default_factory=_default_home_defaults)
    framework_root: Path = field(default_factory=_default_framework_root)

    # -- User data paths (inside patchbay_home) --

    @property
    def workspace(self) -> Path:
        return self.patchbay_home / "workspace"

    @property
    def config_dir(self) -> Path:
        return self.patchbay_home / "config"

    @property
    def config_path(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def sessions_path(self) -> Path:
        return self.patchbay_home / "sessions.json"

    @property
    def cron_jobs_path(self) -> Path:
        return self.patchbay_home / "cron_jobs.json"

    @property
    def webhooks_path(self) -> Path:
        return self.patchbay_home / "webhooks.json"

    @property
    def logs_dir(self) -> Path:
        return self.patchbay_home / "logs"

    @property
    def cron_tasks_dir(self) -> Path:
        return self.workspace / "cron_tasks"

    @property
    def tools_dir(self) -> Path:
        return self.workspace / "tools"

    @property
    def output_to_user_dir(self) -> Path:
        return self.workspace / "output_to_user"

    @property
    def telegram_files_dir(self) -> Path:
        return self.workspace / "telegram_files"

    @property
    def managed_topics_path(self) -> Path:
        """Ids of the topics this bot created. Telegram cannot list them."""
        return self.patchbay_home / "managed_topics.json"

    @property
    def consult_dir(self) -> Path:
        """Working directory for the Consult topic, wiped daily."""
        return self.patchbay_home / "Consult"

    @property
    def uploads_staging_dir(self) -> Path:
        """Where browser uploads wait for confirmation.

        Outside ``workspace`` on purpose: these files are not the agent's to
        see until the user has confirmed where they belong.
        """
        return self.patchbay_home / "uploads_staging"

    @property
    def matrix_files_dir(self) -> Path:
        return self.workspace / "matrix_files"

    @property
    def api_files_dir(self) -> Path:
        return self.workspace / "api_files"

    @property
    def memory_system_dir(self) -> Path:
        return self.workspace / "memory_system"

    @property
    def skills_dir(self) -> Path:
        return self.workspace / "skills"

    @property
    def bundled_skills_dir(self) -> Path:
        """Package-internal skill directory (read-only, ships with patchbay)."""
        return self.home_defaults / "workspace" / "skills"

    @property
    def chat_activity_path(self) -> Path:
        return self.patchbay_home / "chat_activity.json"

    @property
    def named_sessions_path(self) -> Path:
        return self.patchbay_home / "named_sessions.json"

    @property
    def startup_state_path(self) -> Path:
        return self.patchbay_home / "startup_state.json"

    @property
    def inflight_turns_path(self) -> Path:
        return self.patchbay_home / "inflight_turns.json"

    @property
    def env_file(self) -> Path:
        """User-managed ``.env`` for external API secrets."""
        return self.patchbay_home / ".env"

    @property
    def mainmemory_path(self) -> Path:
        return self.memory_system_dir / "MAINMEMORY.md"

    @property
    def join_notification_path(self) -> Path:
        return self.workspace / "JOIN_NOTIFICATION.md"

    # -- Framework paths (bundled with package or repo root) --

    @property
    def config_example_path(self) -> Path:
        """Config example: repo root (dev) or package-bundled (installed)."""
        repo_path = self.framework_root / "config.example.json"
        if repo_path.is_file():
            return repo_path
        return _PKG_DIR / "_config_example.json"

    @property
    def dockerfile_sandbox_path(self) -> Path:
        """Dockerfile.sandbox: repo root (dev) or package-bundled (installed)."""
        repo_path = self.framework_root / "Dockerfile.sandbox"
        if repo_path.is_file():
            return repo_path
        return _PKG_DIR / "_Dockerfile.sandbox"


def resolve_paths(
    patchbay_home: str | Path | None = None,
    *,
    framework_root: str | Path | None = None,
    home_defaults: str | Path | None = None,
) -> PatchbayPaths:
    """Build PatchbayPaths from explicit values, env vars, or defaults.

    Args:
        patchbay_home: User data directory. Falls back to ``$PATCHBAY_HOME`` or ``~/.phoenix-patchbay``.
        framework_root: Repository root. Falls back to ``$PATCHBAY_FRAMEWORK_ROOT``.
        home_defaults: Template directory. Falls back to ``phoenix_patchbay/_home_defaults/``.
    """
    if patchbay_home is not None:
        home = Path(patchbay_home).expanduser().resolve()
    else:
        home = (
            Path(
                os.environ.get("PATCHBAY_HOME", str(Path.home() / ".phoenix-patchbay")),
            )
            .expanduser()
            .resolve()
        )

    if framework_root is not None:
        fw = Path(framework_root).expanduser().resolve()
    else:
        env_fw = os.environ.get("PATCHBAY_FRAMEWORK_ROOT")
        fw = Path(env_fw).resolve() if env_fw else _default_framework_root()

    hd = Path(home_defaults).resolve() if home_defaults is not None else _default_home_defaults()

    return PatchbayPaths(patchbay_home=home, home_defaults=hd, framework_root=fw)
