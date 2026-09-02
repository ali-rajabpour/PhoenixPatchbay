# Deploy

A Linux box that runs coding agents, reachable from a Telegram group. Two
answers and one command.

```bash
git clone https://github.com/ali-rajabpour/PhoenixPatchbay.git
cd PhoenixPatchbay/deploy
cp .env.example .env        # bot token + your Telegram user id
docker compose up -d
```

That is the whole setup. The container writes its own config on first start
from the two environment variables, so nothing asks you a question at a
terminal you do not have.

Then, in Telegram: `/menu` → **Account** to log the Claude CLI in, and
**Folder** to pick where a topic works.

## What you get

- Debian with the agent toolchain: Claude Code, `rtk`, `agent-browser`,
  Chromium, Node, git, ripgrep, build tools.
- The bot, running as an unprivileged user with passwordless `sudo` **inside
  the container** — so the agent can install what it needs without any of it
  reaching the host.
- Claude Code preconfigured with the plugins and hooks that make a
  chat-driven agent affordable to run. See `seed/claude-settings.json`.
- One session per Telegram topic. Five topics are five machines that happen to
  share a chat window.

## The two required answers

| variable | what it is |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_ALLOWED_USER_IDS` | your numeric id, from [@userinfobot](https://t.me/userinfobot) |

**The allowlist is the security boundary.** Anyone not on it is ignored. A bot
with an empty allowlist would answer whoever found it, so the container refuses
to start rather than write that config.

Nothing is published to the network: Telegram long-polling is outbound-only,
so the container is unreachable from the host, the LAN and the internet.

## Where your projects go

Everything lives in the `patchbay_home` volume, mounted at `/home/patchbay`.

```bash
docker compose exec patchbay bash
git clone git@github.com:you/your-project.git ~/projects/your-project
```

Then set `PATCHBAY_PROJECT_ROOTS=projects=/home/patchbay/projects` in `.env`, or
just pick the folder from `/menu` → **Folder** once.

## Everyday commands

```bash
docker compose logs -f patchbay      # what it is doing
docker compose restart patchbay      # restart
docker compose exec patchbay bash    # a shell inside
docker compose down                  # stop (the volume survives)
```

## Upgrading

```bash
docker compose build --no-cache && docker compose up -d
```

`PATCHBAY_REF` in `.env` pins the build to a commit; leaving it unset tracks
`main`. Your config, credentials and projects are in the volume and survive a
rebuild.

## Hardening worth doing

- **Run Docker rootless.** Container root then maps to an unprivileged host
  uid, which is the difference between a mistake inside the container and a
  mistake on your server.
- **Keep the allowlist short.** It is the only thing between a stranger and a
  shell.
- **Give it its own box** if the host runs anything you care about. The
  guardrails in `compose.yaml` (memory, CPU, pids) stop a runaway agent
  starving its neighbours, but they are not isolation.
