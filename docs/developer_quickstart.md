# Developer Quickstart

Fast onboarding path for contributors and junior devs.

## 1) Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional for full runtime validation:

- install/auth at least one provider CLI (`claude`, `codex`, `gemini`, `agy`, `grok`)
- set up a messaging transport:
  - **Telegram**: bot token from @BotFather + user ID (`allowed_user_ids`)
  - **Matrix**: account on any homeserver (homeserver URL, user ID, password, `allowed_users`)
- for Telegram group support, also set `allowed_group_ids`

## 2) Run the bot

```bash
patchbay
```

First run starts onboarding and writes config to `~/.phoenix-patchbay/config/config.json`.

Primary runtime files/directories:

- `~/.phoenix-patchbay/sessions.json`
- `~/.phoenix-patchbay/named_sessions.json`
- `~/.phoenix-patchbay/tasks.json`
- `~/.phoenix-patchbay/chat_activity.json`
- `~/.phoenix-patchbay/cron_jobs.json`
- `~/.phoenix-patchbay/webhooks.json`
- `~/.phoenix-patchbay/startup_state.json`
- `~/.phoenix-patchbay/inflight_turns.json`
- `~/.phoenix-patchbay/SHAREDMEMORY.md`
- `~/.phoenix-patchbay/agents.json`
- `~/.phoenix-patchbay/agents/`
- `~/.phoenix-patchbay/workspace/`
- `~/.phoenix-patchbay/logs/agent.log`

## 3) Quality gates

```bash
pytest
ruff format .
ruff check .
mypy phoenix_patchbay
```

Expected: zero warnings, zero errors.

## 4) Core mental model

```text
Telegram / Matrix / API input
  -> ingress layer (TelegramBot / MatrixBot / ApiServer)
  -> orchestrator flow
  -> provider CLI subprocess
  -> response delivery (transport-specific)

background/async results
  -> Envelope adapters
  -> MessageBus
  -> optional session injection
  -> transport delivery (Telegram or Matrix)
```

## 5) Read order in code

Entry + command layer:

- `phoenix_patchbay/__main__.py`
- `phoenix_patchbay/cli_commands/`

Runtime hot path:

- `phoenix_patchbay/multiagent/supervisor.py`
- `phoenix_patchbay/messenger/telegram/app.py`
- `phoenix_patchbay/messenger/telegram/startup.py`
- `phoenix_patchbay/orchestrator/core.py`
- `phoenix_patchbay/orchestrator/lifecycle.py`
- `phoenix_patchbay/orchestrator/flows.py`

Delivery/task/session core:

- `phoenix_patchbay/bus/`
- `phoenix_patchbay/session/manager.py`
- `phoenix_patchbay/tasks/hub.py`
- `phoenix_patchbay/tasks/registry.py`

Provider/API/workspace core:

- `phoenix_patchbay/cli/service.py` + provider wrappers
- `phoenix_patchbay/api/server.py`
- `phoenix_patchbay/workspace/init.py`
- `phoenix_patchbay/workspace/rules_selector.py`
- `phoenix_patchbay/workspace/skill_sync.py`

## 6) Common debug paths

If command behavior is wrong:

1. `phoenix_patchbay/__main__.py`
2. `phoenix_patchbay/cli_commands/*`

If Telegram routing is wrong:

1. `phoenix_patchbay/messenger/telegram/middleware.py`
2. `phoenix_patchbay/messenger/telegram/app.py`
3. `phoenix_patchbay/orchestrator/commands.py`
4. `phoenix_patchbay/orchestrator/flows.py`

If Matrix routing is wrong:

1. `phoenix_patchbay/messenger/matrix/bot.py`
2. `phoenix_patchbay/messenger/matrix/transport.py`
3. `phoenix_patchbay/orchestrator/flows.py`

If background results look wrong:

1. `phoenix_patchbay/bus/adapters.py`
2. `phoenix_patchbay/bus/bus.py`
3. `phoenix_patchbay/messenger/telegram/transport.py` (or `phoenix_patchbay/messenger/matrix/transport.py`)

If tasks are wrong:

1. `phoenix_patchbay/tasks/hub.py`
2. `phoenix_patchbay/tasks/registry.py`
3. `phoenix_patchbay/multiagent/internal_api.py`
4. `phoenix_patchbay/_home_defaults/workspace/tools/task_tools/*.py`

If API is wrong:

1. `phoenix_patchbay/api/server.py`
2. `phoenix_patchbay/orchestrator/lifecycle.py` (API startup wiring)
3. `phoenix_patchbay/files/*` (allowed roots, MIME, prompt building)

## 7) Behavior details to remember

- `/stop` and `/stop_all` are pre-routing abort paths in middleware/bot.
- `/new` resets the configured default-provider bucket for the active `SessionKey`.
- `/reset` resets the currently active provider bucket for the active `SessionKey`.
- session identity is transport-aware: `SessionKey(transport, chat_id, topic_id)`.
- `/model` inside a topic updates only that topic session (not global config).
- task tools now support permanent single-task removal via `delete_task.py` (`/tasks/delete`).
- `create_task.py --priority interactive|background|batch` controls whether a task bypasses the per-chat concurrency cap.
- `ask_agent_async.py` supports `--reply-to AGENT` and `--silent` for automated multi-agent pipelines.
- task routing is topic-aware via `thread_id` and `PATCHBAY_TOPIC_ID`.
- API auth accepts optional `channel_id` for per-channel session isolation.
- startup recovery uses `inflight_turns.json` + recovered named sessions.
- auth allowlists (`allowed_user_ids`, `allowed_group_ids`) are hot-reloadable.
- `patchbay agents add` is a Telegram-focused scaffold; Matrix sub-agents are supported through `agents.json` or the bundled agent tool scripts.

Continue with `docs/system_overview.md` and `docs/architecture.md` for complete runtime detail.
