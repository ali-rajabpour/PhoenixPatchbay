# cli_commands/

CLI command implementation package extracted from `__main__.py`.

## Files

- `cli_commands/lifecycle.py`: `start_bot`, `stop_bot`, `cmd_restart`, `upgrade`, `uninstall`, `_re_exec_bot`
- `cli_commands/status.py`: `print_status`, `print_usage`
- `cli_commands/service.py`: `patchbay service ...`
- `cli_commands/docker.py`: `patchbay docker ...`
- `cli_commands/api_cmd.py`: `patchbay api ...`
- `cli_commands/agents.py`: `patchbay agents ...`
- `cli_commands/install.py`: `patchbay install <extra>`

## Role in runtime

`phoenix_patchbay/__main__.py` is now a thin entrypoint:

- argument parsing + command dispatch
- config helpers (`_is_configured`, `load_config`, `run_bot`)
- imports/re-exports command handlers from `cli_commands/*`

This keeps lifecycle logic testable and prevents command monolith growth.

## Command groups

- lifecycle: `patchbay`, `stop`, `restart`, `upgrade`, `uninstall`, onboarding/reset flow
- status/help/version: `patchbay status`, `patchbay help`, `patchbay --version` / `-V`
- service: install/status/start/stop/logs/uninstall wrapper for platform backends
- docker: enable/disable/rebuild/mount/unmount/mounts/extras/extras-add/extras-remove
- api: enable/disable direct WebSocket API block in config
- agents: list/add/remove sub-agent entries in `agents.json`
- install extras: `patchbay install <extra>` for optional Python extras (`matrix`, `api`)

## Notable behavior details

- `stop_bot()` stops service first, then PID instance, then remaining patchbay processes, then Docker container (if enabled).
- `start_bot()` calls `load_config()` and starts `AgentSupervisor` via `run_bot()`.
- `patchbay agents add <name>` is an interactive Telegram-focused scaffold; Matrix sub-agents are configured via `agents.json` or the bundled agent tool scripts.
- `patchbay restart` always runs `stop_bot()` and then re-execs the current process.
- `patchbay --version` / `-V` exits immediately from `__main__.py` without touching config loading or runtime startup.
- exit code `42` is the in-app runtime/supervisor restart signal (`/restart`, service-managed restarts), not the behavior of the CLI `patchbay restart` command.
- `status.py` currently counts errors from latest `patchbay*.log`; runtime primary log file is `~/.phoenix-patchbay/logs/agent.log`.

## Why this matters for docs

When documenting CLI behavior, reference `cli_commands/*` for command internals.
Use `__main__.py` as the dispatch map, not as the implementation source.
