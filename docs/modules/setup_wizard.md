# Setup Wizard and CLI Entry

Covers `patchbay` command behavior, onboarding flow, and lifecycle commands.

## Files

- `phoenix_patchbay/__main__.py`: CLI dispatch + config helpers + `run_bot`
- `phoenix_patchbay/cli_commands/lifecycle.py`: start/stop/restart/upgrade/uninstall logic
- `phoenix_patchbay/cli_commands/status.py`: `patchbay status` + `patchbay help`
- `phoenix_patchbay/cli_commands/service.py`: service command routing
- `phoenix_patchbay/cli_commands/docker.py`: docker subcommands
- `phoenix_patchbay/cli_commands/api_cmd.py`: API enable/disable commands
- `phoenix_patchbay/cli_commands/agents.py`: sub-agent registry commands
- `phoenix_patchbay/cli_commands/install.py`: optional extras installer (`patchbay install <extra>`)
- `phoenix_patchbay/infra/docker_extras.py`: optional Docker package registry + Dockerfile generation
- `phoenix_patchbay/cli/init_wizard.py`: onboarding + smart reset

## CLI commands

- `patchbay`: start bot (auto-onboarding if needed)
- `patchbay onboarding` / `patchbay reset`: onboarding flow (with smart reset when configured)
- `patchbay status`
- `patchbay stop`
- `patchbay restart`
- `patchbay upgrade`
- `patchbay uninstall`
- `patchbay service <install|status|start|stop|logs|uninstall>`
- `patchbay docker <rebuild|enable|disable|mount|unmount|mounts|extras|extras-add|extras-remove>`
- `patchbay api <enable|disable>`
- `patchbay agents <list|add|remove>`
- `patchbay install <matrix|slack|api>`
- `patchbay help`

## Configuration gate

`_is_configured()` checks all active transports:

- when `transports` is set: every listed transport must pass its checker
- when `transports` is empty: falls back to single `transport`

- **Telegram** (default): valid non-placeholder `telegram_token` + non-empty `allowed_user_ids`
- **Matrix**: non-empty `homeserver` + non-empty `user_id`

`allowed_group_ids` controls group authorization but does not satisfy startup configuration alone.

## Onboarding flow (`run_onboarding`)

1. banner
2. provider install/auth check
3. disclaimer
4. **transport selection** (Telegram or Matrix)
   - After initial setup, multiple transports can run in parallel via
     the `transports` array in `config.json` (see [config.md](../config.md))
5. transport-specific credentials:
   - Telegram: bot token prompt + user ID prompt
   - Matrix: homeserver URL + bot user ID + password + allowed users
6. Docker choice
7. Docker extras selection (only when Docker enabled)
8. timezone choice
9. write merged config + initialize workspace
10. optional service install

Step 7 shows a Rich table of optional AI/ML packages grouped by category (Audio/Speech, Vision/OCR, Document Processing, Scientific/Data, ML Frameworks, Web/Browser) with descriptions and size estimates. Users select via `questionary.checkbox`. Transitive dependencies are auto-resolved.

Return semantics:

- `True` when service install was completed
- `False` otherwise

Caller behavior:

- default `patchbay`: onboarding if needed, then foreground start unless service install path returned `True`
- `patchbay onboarding/reset`: calls `stop_bot()` first, then onboarding, then same service/foreground logic

## Lifecycle command behavior

### `stop_bot()`

Shutdown sequence:

1. stop installed service (prevents auto-respawn)
2. kill PID-file instance
3. kill remaining patchbay processes
4. short lock-release wait on Windows
5. stop Docker container when enabled

### Restart

- `cmd_restart()` = `stop_bot()` + process re-exec
- restart code `42` is used for service-managed restart semantics

### Upgrade

- dev installs: no self-upgrade, show guidance
- upgradeable installs: stop -> upgrade pipeline -> verify version -> restart

### Uninstall

- stop bot/service
- optional Docker image cleanup
- remove `~/.phoenix-patchbay` via robust filesystem helper
- uninstall package (`pipx` or `pip`)

## Status panel

`patchbay status` shows:

- running state/PID/uptime
- provider/model
- Docker state
- error count from newest `patchbay*.log`
- key paths
- sub-agent status table when configured (live health if bot is running)

Note: runtime primary log file is `~/.phoenix-patchbay/logs/agent.log`; status error counter is currently `patchbay*.log`-based.

## Docker command notes

`patchbay docker ...` commands update `config.json` and/or container/image state.

- mount/unmount paths are resolved and validated
- mount list shows host path, container target, status
- restart/rebuild is required for mount flag changes to affect running container

### Docker extras management

- `patchbay docker extras` shows a table of all available optional packages with their status (selected / —) and a hint to rebuild after changes.
- `patchbay docker extras-add <id>` adds an extra (+ transitive dependencies) to `config.json`.
- `patchbay docker extras-remove <id>` removes an extra from `config.json`, warns about reverse dependencies.
- without `<id>`, `extras-add` / `extras-remove` list available choices.
- after add/remove, the user must run `patchbay docker rebuild` to apply changes to the Docker image.
- selected extras are compiled into additional `RUN` blocks appended to the base `Dockerfile.sandbox` at build time.

## API command notes

`patchbay api enable`:

- requires PyNaCl
- writes/updates `config.api`
- generates token when missing

`patchbay api disable`:

- sets `config.api.enabled=false` (keeps token/settings)

Both require bot restart to apply.

## Service command routing

`patchbay service ...` delegates to platform backends:

- Linux: systemd user service
- macOS: launchd Launch Agent
- Windows: Task Scheduler

Detailed backend behavior: [service_management](service_management.md)

`patchbay service logs`:

- Linux: `journalctl --user -u patchbay -f`
- macOS/Windows: tail from `~/.phoenix-patchbay/logs/agent.log` (fallback newest `*.log`)
