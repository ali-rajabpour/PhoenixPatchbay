<p align="center">
  <img src="phoenix_patchbay/messenger/telegram/patchbay_images/logo_text.png" alt="Phoenix Patchbay" width="100%" />
</p>

<h1 align="center">Phoenix Patchbay</h1>

<p align="center">
  <strong>Claude Code, Codex CLI, Gemini CLI, Antigravity CLI, and Grok Build as your coding assistant — on Telegram, Matrix, and Slack.</strong><br>
  A machine that runs agents, with chat where the terminal would be. One topic is one session.<br>
  Uses only official CLIs. Nothing spoofed, nothing proxied.
</p>

<p align="center">
  <a href="https://pypi.org/project/phoenix-patchbay/"><img src="https://img.shields.io/pypi/v/phoenix-patchbay?color=blue" alt="PyPI" /></a>
  <a href="https://pypi.org/project/phoenix-patchbay/"><img src="https://img.shields.io/pypi/pyversions/phoenix-patchbay?v=1" alt="Python" /></a>
  <a href="https://github.com/ali-rajabpour/PhoenixPatchbay/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ali-rajabpour/PhoenixPatchbay" alt="License" /></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> &middot;
  <a href="#how-chats-work">How chats work</a> &middot;
  <a href="#commands">Commands</a> &middot;
  <a href="docs/README.md">Docs</a> &middot;
  <a href="#contributing">Contributing</a>
</p>

---

## About this project

**Phoenix Patchbay** turns a always-on Linux box into a machine that runs coding agents,
with Telegram where the terminal would be. Each topic in a group is one session, named
after the topic, in that topic's folder — so five topics are five machines that happen to
share a chat window.

Built and maintained by **[Ali Rajabpour Sanati](https://Rajabpour.com)**, and running
24/7 against live production projects rather than as a demo.

### Provenance

Phoenix Patchbay is a substantially modified derivative of
[ductor](https://github.com/PleasePrompto/ductor) by PleasePrompto, MIT licensed. Both
copyright notices are kept in [`LICENSE`](LICENSE), and [`NOTICE`](NOTICE) records what
came from where.

What is original to this project: the one-topic-one-session model, the queue and
interrupt behaviour, the handoff system, the per-topic isolation of stopping and
queueing, and the removal of background task delegation. What came from upstream: much
of the transport, CLI provider and workspace machinery.

It is **not** a drop-in upgrade of the original — background task delegation, `/tasks`,
the task tools and the memory reflection cadence were removed outright, and that removal
is the point rather than a side effect. See *One topic, one session* below.

### What this project adds

**One topic, one session.** A topic is a session, named after the topic, in the
topic's folder — the same way a terminal window is a session. Work stays in it: nothing
is handed to a detached run that has to be told what it is doing. The previous design
pushed anything longer than about thirty seconds into a background task with its own
session, which paid the CLI's ~38K-token startup a second time and then spent its first
dozen turns rediscovering the project because its brief said it had no prior context.
Two ordinary messages measured 2.3M token-units, 80% of it outside the chat. A message
sent while a turn is running is queued behind it, per topic, so a long run in one topic
never blocks another.

**Stop, which is Ctrl+C.** A running turn carries a `⏹ Stop` button. It sends SIGINT and
whatever is queued behind the turn starts immediately — the same two behaviours the key
has in a terminal. Verified against the real binary before it was built: interrupting a
live tool call leaves no unanswered `tool_use`, the CLI records the interruption itself,
and `--resume` still works.

**A turn's clock measures silence, not duration.** Work that may legitimately run all
night cannot be capped by a stopwatch, so the deadline sits three hours after the last
line of output, wherever that was. A finished step that reports in resets it for the
next one. It exists only to free a topic whose CLI has wedged.

**Handoffs, written as the work happens.** The file lives in the project folder —
`handoffs/`, excluded through `.git/info/exclude` and verified with `git check-ignore` on
every write, so a working note can never reach a commit. Its skeleton and its per-turn
log are written by code rather than asked for: the model was given the path, the sections
and an explicit instruction, and across eleven turns wrote nothing, so that instruction
was removed rather than kept as decoration. Judgement is spent on the write-up instead,
where it is the only thing being asked for — and that now runs when a few turns' work has
accumulated and no message is waiting, not only at `/compact` and `/clear`. It costs about
as much as a real turn, so given a Gemini key it runs there rather than on the
subscription doing the work: a separate call, handed the transcript since the last
write-up with tool results stripped, returning a document that patchbay writes itself.
The key is pasted into `/settings` from the chat and checked against Google before it is
stored, so nobody has to open an SSH session as root to change a preference.

**Every screen can be left.** Selectors and file-browser views carry a `◀︎ Menu` and a
`✕ Close` on the way out, attached once at the point screens reach Telegram rather than
in each builder, so a screen added later inherits them and cannot become the one dead end.

**Working directories, and consent about them.** A conversation is bound to a project
folder by tapping a button, once, and the binding is a record of consent rather than a
guess. Folder names are never inferred from topic names — that mechanism failed silently
after every restart and ran work in the wrong directory with nothing said. Every injected
prompt path is anchored to the workspace at the CLI choke point, so an instruction to
write `memory_system/MAINMEMORY.md` cannot land inside a user's git tree. A forum's
General thread can never hold a binding at all: its messages carry no
`message_thread_id`, so binding one there let a message typed outside a topic start a
fresh conversation in another topic's project folder.

**A file browser over the project roots.** Browse bound directories, pull and push, send
files up and pull them down, and rename, create, delete, move or copy behind an explicit
Manage gate — all from a phone, as `/files`. Move and copy mark a source, then paste
into wherever you navigate to; a paste **never overwrites**, and a folder cannot be
pasted inside its own subtree. Both are refusals rather than confirmations, because a
replace dialog agreed to with a thumb is how a file disappears without anyone noticing.
A `📋 Path` button shows any file's or folder's absolute path in a tap-to-copy block,
so a location can be handed to an agent in a prompt without moving the file anywhere.
The old "ask the agent about this folder" button is gone: it spent a model turn listing
a directory already on screen, and it was the only code path that injected a fabricated
user message into a real session.

**A Consult topic that is genuinely disposable.** Created and pinned by the bot,
scoped to its own directory, wiped on a schedule, and running as its own unix account so
the isolation is enforced by the kernel rather than by a sentence in a prompt.

**Phone-shaped UI.** An inline menu behind a single toggle, a `/` picker trimmed to what
fits on a screen, and button labels that never inline into a sentence.

**Accounts, personas and skills.** `/account` switches the credential store — moving
`CLAUDE_SECURESTORAGE_CONFIG_DIR` alone, so sessions, skills and MCP stay shared and
`--resume` continues the same conversation on the other subscription. A persona gate asks
which agent governs a conversation instead of picking something plausible, and `/skills`
browses what is installed.

### Running it

Deployment lives outside this repository: the bot runs as an unprivileged user on a
rootless Docker daemon, with credentials and per-project access managed on the host.
Nothing here assumes that setup — `pip install patchbay` and the upstream quick start below
still work unchanged.

---

If you want to control Claude Code, Google's Gemini CLI, OpenAI's Codex CLI, Antigravity CLI, or xAI Grok Build via Telegram, Matrix, or Slack, build automations, or manage multiple agents easily — patchbay is the right tool for you. The messaging layer is modular: Telegram, Matrix, and Slack ship today, and new transports plug into the same transport-agnostic core.

patchbay runs on your machine and sends simple console commands as if you were typing them yourself, so you can use your active subscriptions (Claude Max, Google AI Ultra, etc.) directly. No API proxying, no SDK patching, no spoofed headers. Just the official CLIs, executed as subprocesses, with all state kept in plain JSON and Markdown under `~/.phoenix-patchbay/`.

## Quick start

```bash
pipx install patchbay    # or: uv tool install patchbay
patchbay
```

The onboarding wizard handles CLI checks, transport setup, timezone, optional Docker, and optional background service install.

**Requirements:** Python 3.11+, at least one CLI installed (`claude`, `codex`, `gemini`, `agy`, or `grok`), and either:

- a Telegram Bot Token from [@BotFather](https://t.me/BotFather), or
- a Matrix account on a homeserver (homeserver URL, user ID, password/access token), or
- a Slack bot token + Socket Mode app token (plus the Slack app scopes/events listed in [`docs/installation.md#slack-setup`](docs/installation.md#slack-setup))

For Matrix support: `patchbay install matrix` — see [Matrix setup guide](docs/matrix-setup.md).
For Slack support: `pip install "patchbay[slack]"`, then follow [`docs/installation.md#slack-setup`](docs/installation.md#slack-setup) and configure `slack.bot_token` + `slack.app_token`.

Detailed setup: [`docs/installation.md`](docs/installation.md)

## How chats work

patchbay gives you multiple ways to interact with your coding agents. Each level builds on the previous one.

### 1. Single chat (your main agent)

This is where everyone starts. You get a private 1:1 chat with your bot (Telegram or Matrix). Every message goes to the CLI you have active (`claude`, `codex`, `gemini`, `agy`, or `grok`), responses stream back in real time.

```text
You:   "Explain the auth flow in this codebase"
Bot:   [streams response from Claude Code]

You:   /model
Bot:   [interactive model/provider picker]

You:   "Now refactor the parser"
Bot:   [streams response, same session context]
```

This single chat is all you need. Everything else below is optional.

### 2. Groups with topics (multiple isolated chats)

**Telegram:** Create a group, enable topics (forum mode), and add your bot.
**Matrix:** Invite the bot to multiple rooms — each room is its own context.

Every topic (Telegram) or room (Matrix) becomes an isolated chat with its own CLI context.

```text
Group: "My Projects"
  ├── General           ← own context (isolated from your single chat)
  ├── Topic: Auth       ← own context
  ├── Topic: Frontend   ← own context
  ├── Topic: Database   ← own context
  └── Topic: Refactor   ← own context
```

That's 5 independent conversations from a single group. Your private single chat stays separate too — 6 total contexts, all running in parallel.

Each topic can use a different model. Run `/model` inside a topic to change just that topic's provider.

All chats share the same `~/.phoenix-patchbay/` workspace — same tools, same memory, same files. The only thing isolated is the conversation context.

> **Telegram note:** The Bot API has no method to list existing forum topics.
> patchbay learns topic names from `forum_topic_created` and `forum_topic_edited`
> events — pre-existing topics show as "Topic #N" until renamed.
> This is a Telegram limitation, not a patchbay limitation.
>
> Folder bindings do not depend on those names: they are keyed by chat and
> topic id, so a topic patchbay cannot name still works, and renaming one never
> changes where its work happens.

### 3. Named sessions (extra contexts within any chat)

Need to work on something unrelated without losing your current context? Start a named session. It runs inside the same chat but has its own CLI conversation.

```text
You:   "Let's work on authentication"        ← main context builds up
Bot:   [responds about auth]

/session Fix the broken CSV export            ← starts session "firmowl"
Bot:   [works on CSV in separate context]

You:   "Back to auth — add rate limiting"     ← main context is still clean
Bot:   [remembers exactly where you left off]

@firmowl Also add error handling              ← follow-up to the session
```

Sessions work everywhere — in your single chat, in group topics, in sub-agent chats. Think of them as opening a second terminal window next to your current one.

### 4. Long work (it stays in the conversation)

There is no background-task system. Work that takes minutes or hours runs in the topic's
own session, in front of you, the way it does in a terminal.

```text
You:   "Deploy the plugin and verify it live"
Bot:   [works — tool calls stream as they happen, ⏹ Stop on the message]

You:   "actually check staging first"        ← arrives mid-run
Bot:   ⏳ queued — it runs the moment the turn finishes

[⏹ Stop]                                     ← SIGINT; the queued message starts now
```

Queueing and stopping are scoped to the topic, so a long run in one topic never blocks
or stops another. A turn has no duration limit; it ends when the work does, when you
stop it, or after three hours with no output at all.

### 5. Sub-agents (fully isolated second agent)

Sub-agents are completely separate bots — own chat, own workspace, own memory, own CLI auth, own config settings (heartbeat, timeouts, model defaults, etc.). Each sub-agent can use a different transport (e.g. main on Telegram, sub-agent on Matrix).

```bash
patchbay agents add codex-agent    # creates a new bot (needs its own BotFather token)
```

```text
Your main chat (Claude):        "Explain the auth flow"
codex-agent chat (Codex):       "Refactor the parser module"
```

Sub-agents live under `~/.phoenix-patchbay/agents/<name>/` with their own workspace, tools, and memory — fully isolated from the main agent.

Agents can talk to each other. This is a message on the inter-agent bus, not a
background task — the sub-agent answers in its own session and the reply comes back:

```text
Main chat:  "Ask codex-agent to write tests for the API"
  → Claude sends the task to Codex
  → Codex works in its own workspace
  → Result flows back to your main chat
```

### Comparison

| | Single chat | Group topics | Named sessions | Sub-agents |
|---|---|---|---|---|
| **What it is** | Your main 1:1 chat | One topic = one session | Extra context in any chat | Separate bot, own everything |
| **Context** | One per provider | One per topic per provider | Own context per session | Fully isolated |
| **Workspace** | `~/.phoenix-patchbay/` | Shared with main | Shared with parent chat | Own under `~/.phoenix-patchbay/agents/` |
| **Config** | Main config | Shared with main | Shared with parent chat | Own config (heartbeat, timeouts, model, ...) |
| **Setup** | Automatic | Create group + enable topics | `/session <prompt>` | Telegram: `patchbay agents add`; Matrix: `agents.json` / tool scripts |

### How it all fits together

```text
~/.phoenix-patchbay/                          ← shared workspace (tools, memory, files)
  │
  ├── Single chat                   ← main agent, private 1:1
  │     ├── main context
  │     └── named sessions
  │
  ├── Group: "My Projects"          ← same agent, same workspace
  │     ├── General (own context)
  │     ├── Topic: Auth (own session, own model)
  │     ├── Topic: Frontend (own context)
  │     └── each topic can have named sessions too
  │
  └── agents/codex-agent/           ← sub-agent, fully isolated workspace
        ├── own single chat
        ├── own group support
        └── own named sessions
```

## Features

- **Multi-transport** — run Telegram, Matrix, and Slack simultaneously, or pick any one
- **Multi-language** — UI in English, Deutsch, Nederlands, Français, Русский, Español, Português
- **Real-time streaming** — live message edits (Telegram) or segment-based output (Matrix)
- **Telegram reasoning + tool UX controls** — optional reasoning stream, live tool progress, and separate thinking indicator controls
- **Quoted-reply context** — replying to a message (Telegram) carries the cited text into the agent prompt, so follow-ups like "expand on this" keep their reference
- **Five coding agents** — Claude Code, Codex CLI, Gemini CLI (API key / Code Assist license; Google ended free individual-account access on 2026-06-18), Antigravity (`agy`), and Grok Build (`grok`), switchable per chat/topic with `/model` (never blocks, even during active processes)
- **Per-conversation folders** — `project_roots` lists the directories you are willing to work in; a conversation is *bound* to one of them by tapping `📌 Use this folder` in `/files`, or by answering the picker the first time you use it. Bindings are keyed by session, so renaming a topic cannot break them and a restart cannot forget them. Change one later with `/folder`
- **The bot's own files stay findable** — when a conversation runs in a project directory, every prompt naming a workspace path (`tools/`, `memory_system/`, `cron_tasks/`, `user_tools/`, …) is rewritten to an absolute path at the point the CLI is invoked. Without it an agent looks for tools that are not under its cwd and concludes it is in the wrong place — and an instruction to update `memory_system/MAINMEMORY.md` resolves *inside your repository*
- **Managed topics** (`managed_topics`, **off by default**) — when enabled, patchbay creates a `Consult` topic in each configured group and keeps a notice in it and in General, verifying both on every start. The General notice is pinned; the Consult one cannot be — `pinChatMessage` takes no `message_thread_id`, so a bot cannot pin inside a forum topic — and is instead the first message of a topic that is recreated on every wipe. Consult gets its own working directory at `~/.phoenix-patchbay/Consult`, carrying a `CLAUDE.md` that tells the agent to stay inside it. That is an instruction the agent follows, **not a sandbox** — the CLI runs as your user and a working directory is not a boundary. Leave this off unless you want a bot that creates topics and pins messages in your group Inside Consult the file manager and the folder picker are narrowed to that topic's own directory — unlike the instruction in its `CLAUDE.md`, that part is enforced, because the browser is patchbay's own code With a `consult` unix account present, the CLI for that topic is dropped to it — the project tree is `0750` and the account is not in the bot's group, so it cannot read your repositories whatever the rule persuades it to try. It still shares the credential store, because the CLI has to authenticate: the isolation is from your projects, not from your token or the network
- **Scheduled Consult wipe** (`/consult`) — the Consult topic is deleted and recreated on a schedule you pick from Telegram: hourly, every 6 hours, daily at a set hour, weekly, or never. Deleting the topic clears its files, its messages *and* its session in one step, since the replacement gets a new topic id. The pinned notice is regenerated from the schedule, so it never promises a wipe that is not running
- **Rename, new folder and delete** — behind a `🛠 Manage` button, so nothing that changes files sits on the row you tap to browse. Renaming and creating ask for the name as a message and show it back for approval before writing. Deleting takes two confirmations and states what will go — file count and real size, not a rounded one. Two cases are refused outright rather than confirmed: a configured project root, and any directory containing `.git`, whose untracked files exist nowhere else
- **Multi-account Claude** — map several credential stores in `claude_accounts` and switch with `/account`; sessions and skills stay shared, so a rate-limited conversation continues on the other subscription via `--resume`
- **Skill browser** — `/skills` groups every loadable skill by plugin and copies `/name ` to your clipboard on tap, which is the only way to reach skills marked `disable-model-invocation`. Discovery follows `enabledPlugins` and the plugin registry, so stale versions and disabled plugins are not listed
- **File manager over your projects** — `/files` opens in the folder this conversation is bound to, or lists `~/.phoenix-patchbay` alongside every directory in `project_roots` when it is not bound, with tap-to-navigate, breadcrumbs, `Back` to the parent directory and `Home` to the folder this conversation is bound to (the list of roots when it is not bound). Only directories get a button; files are reached through `⬇️ Download`, which offers a single file or the whole folder as a zip, so a folder of any size stays a screen you can aim at. Nested roots collapse into their parent so the picker stays short
- **Button menu** (`/menu`) — Telegram's toggle beside the input box is bound to reply keyboards and cannot be pointed elsewhere, so the panel holds a single `/menu` button and everything after it is an inline keyboard. Exactly one command is ever sent as text, and it is deleted on arrival; every menu action is a callback, so nothing the menu does reaches the agent and nothing has to be intercepted to keep it out. Items are fixed rather than filtered — a button that appears and disappears reads as a broken screen — and the current folder, persona and model are shown in the header instead The thirteen commands the menu covers are dropped from Telegram's `/` picker — they still work when typed and are still listed by `/help`, which keeps the picker to the thirteen that are urgent, take arguments, or have no button
- **Uploads land where the work is** — a file sent to a topic is saved into that topic's `project_roots` directory instead of a shared media folder, and the bot replies with where it put it
- **Upload into any folder you can browse** — `⬆️ Upload here` opens an upload for the directory you are looking at. Files are staged and listed, overwrites are flagged, and nothing is written until you confirm; `📦 Send a folder (.zip)` unpacks an archive into that listing first. Archives are validated before extraction (no path traversal, no symlink entries, size and entry ceilings), and staging is discarded on cancel and swept daily
- **Pull and push from the browser** — a directory inside a git repository gains `⤓ Pull` and `⤒ Push`. Push is inert when the branch matches its upstream, and asks for confirmation against the list of commits it would publish. Pull is `--ff-only`, so a divergence is reported rather than merged unnoticed
- **Personas** — when `persona_prompt` is on, a conversation that has not chosen a persona asks which of your Claude Code agents should handle it, holds your message until you pick, then runs it under `--agent`. Change it any time with `/persona`; `/clear` clears it. Nothing is inferred and there is no default; installations without agents never see the prompt
- **Plugin scope per persona, per conversation** (`/plugins`) — every plugin a Claude Code installation has enabled loads into every run, whether that run needs it or not, and a plugin costs its skills, agents and MCP connections on the turn it loads. A persona can now say what it actually needs, in `<config>/personas/<name>.settings.json`, and one conversation can disagree with its persona from the `/plugins` keyboard. The document handed to `--settings` is the installation's own `settings.json` with `enabledPlugins` replaced — never one assembled from scratch, because that same file carries the permission allowlist and the hooks enforcing the read guard, and dropping those silently would be a security regression wearing a token-saving hat. When nothing narrows the set, no file is written and no flag is passed. **Interactive Claude Code cannot do this well**: it fixes its plugin set when the process starts, so a plugin enabled mid-session does nothing until you restart and one disabled mid-session keeps working. Every turn here is a fresh `claude -p` process, so a tap applies to your next message with nothing to restart and nothing left running after you switch it off
- **One session per topic** — a topic is a session, named after the topic, in the topic's folder. Long work runs inside it rather than being handed to a detached run that must be told what it is doing. A message typed during a turn is queued behind it, per topic
- **`⏹ Stop` on a running turn** — SIGINT, after which the queued message starts immediately. The CLI records the interruption itself, so the session stays resumable
- **Idle deadline, not a stopwatch** — a turn ends when the work ends, when you stop it, or after three hours with nothing printed at all. Cron, webhook and injected runs keep their own duration cap (`cli_timeout`)
- **Handoffs, written as you go** — every conversation keeps one in its project's `handoffs/`, excluded via `.git/info/exclude` and verified with `git check-ignore` on every write. What was asked is recorded by code on each turn; the write-up — objective, state, decisions, dead ends, what is next, each claim carrying a path or a commit — happens once a few turns' worth of work has piled up and you have not already sent the next message. `/compact` and `/clear` write one first too; `/handoff` shows the current one; `/clear` archives it outside the folder rather than deleting it
- **An append-only history beside every handoff** — the handoff is rewritten at each write-up and is lossy on purpose: it is injected at every session start and after every compaction, so it has to stay small, and by month two the reasoning behind a week-one decision is one line. Before anything overwrites it, the whole document is appended to `handoffs/<conversation>.history.md` — never rewritten, never injected, never deleted, not even by `/clear`. It is not context, so its size costs nothing; what the agent gets on every turn is one line naming the exact file, and it searches that file when the handoff refers to something it no longer explains. Identical revisions are skipped, so a failed write-up does not fill it with copies, and it is refused outright if git would track it — the guard runs *before* the append, because a handoff can be deleted and rewritten but a history cannot
- **The write-up can run on Gemini instead of your coding subscription** — paste a key into `/settings` (free from [AI Studio](https://aistudio.google.com/apikey), or `GEMINI_API_KEY` for a fresh deployment) and the handoff is written by a separate Gemini call rather than by resuming the session that did the work. Measured at ~$0.17 a time on the session's own subscription, which is real money on a busy day and invisible in the per-session totals. The writer was not in the conversation, so it is handed the transcript since the last write-up with tool *results* stripped — decisions, not the output of every grep. It returns the document and patchbay writes it, so an answer that is not a handoff leaves the good one alone. **URLs and non-Latin strings never reach the model at all** — they are lifted out, replaced with plain ASCII placeholders, and substituted back verbatim, because a model asked to retype a URL will eventually drop a character from it. Once it did: an Arabic slug came back one letter short, a 404 in a document someone would later trust. The model arranges the handoff; it does not transcribe the literals. The model is pinned to `gemini-3.5-flash-lite` and is deliberately not configurable — the write-up has a fixed shape, so which model does it is an implementation detail, and at ~$0.009 a time against ~$0.17 in-session the choice is already 19× cheaper without asking anyone to tune it. It runs in the shared workspace rather than your project folder: it reads no files, so a summariser with tool access to a repository is blast radius nobody asked for. Verified end to end — three turns of real work, then a write-up naming the file, the rate change and the self-check that proves it. With no key set, nothing changes: the write-up resumes the session as before
- **`/settings`, so a preference never needs an SSH session** — values that used to mean editing JSON on the host as root are set from the chat. Each row carries its own state (`✅ set` / `⚠️ not set`) with the cost of leaving it unset written next to it, and a secret is masked to `AIza••••••••4f2` — never echoed in full. **A key is checked against the service before it is stored**, so `✅` means Google accepted it, not that it matched a pattern: a spent quota says so rather than claiming the key is bad, and "could not reach Google" never counts as success. A stored key keeps a `🔄 Test` button, because keys get revoked without any screen changing. Your message is deleted the moment it is read — before validation, since a mistyped secret is still a secret — though it does still pass through Telegram to get there, which the prompt says before you paste
- **Memory scoped by reach** — `MAINMEMORY.md` holds only what is true across every project; anything about one codebase lives in that project's own knowledge file, so a topic does not pay for another topic's details on every turn
- **A way out of every screen** — `◀︎ Menu` and `✕ Close` on selectors and browser views, attached where screens reach Telegram so a new screen inherits them
- **Persistent memory** — plain Markdown files that survive across sessions
- **Memory maintenance** — pre-compaction flush and LLM-driven compaction. The reflection cadence was removed: it spent a model turn on a schedule rather than on a need
- **Cron jobs** — in-process scheduler with timezone support, per-job overrides, optional silent-on-success, result routing to originating chat
- **Webhooks** — `wake` (inject into active chat) and `cron_task` (isolated one-shot run) modes
- **Heartbeat** — proactive checks with per-target settings, group/topic support, chat validation
- **Image processing** — auto-resize and WebP conversion for incoming images (configurable)
- **Files you send are not read unless you say so** (container image) — a PDF or photo sent to a topic is usually meant to be placed, attached or uploaded, and one curious read of a PDF put 629 KB into a transcript that every later turn then paid for again. The agent has to ask first. Once you agree, it gets a 1024px copy of a photo or a PDF's extracted text rather than the original. Reading it through a shell is blocked the same way, while `mv`, `cp`, `ls`, `zip` and the rest keep working — it is a cost guard, not a sandbox
- **Media transcription hooks** — configurable external audio/video transcription commands for bundled media tools
- **Notification routing** — startup/upgrade lifecycle messages can target specific chats/topics
- **Telegram status reactions** — stage-aware emoji tracker on the user message while the agent works
- **Config hot-reload** — most settings update without restart (including language, scene, image)
- **Docker sandbox** — optional sidecar container with configurable host mounts
- **Service manager** — Linux (systemd), macOS (launchd), Windows (Task Scheduler)
- **Cross-tool skill sync** — shared skills across `~/.claude/`, `~/.codex/`, `~/.gemini/`, `~/.grok/` (globally or per-provider toggleable)

## Messenger support

Telegram is the primary transport — full feature set, battle-tested, zero extra dependencies.

| Messenger | Status | Streaming | Buttons | Install |
|---|---|---|---|---|
| **Telegram** | primary | Live message edits | Inline keyboards | `pip install patchbay` |
| **Matrix** | supported | Segment-based (new messages) | Emoji reactions | `patchbay install matrix` |
| **Slack** | supported | Non-streaming | Native threads | `pip install "patchbay[slack]"` |

Both transports can run **in parallel** on the same agent:

```json
{"transport": "telegram"}
{"transport": "matrix"}
{"transport": "slack"}
{"transports": ["telegram", "slack"]}
```

### Modular transport architecture

Each messenger is a self-contained module under `messenger/<name>/` implementing a
shared `BotProtocol`. The core (orchestrator, sessions, CLI, cron, etc.) is completely
transport-agnostic — it never knows which messenger delivered the message.

Adding a new messenger (Discord, Slack, Signal, ...) means implementing `BotProtocol`
in a new sub-package and registering it — the rest of patchbay works without changes.
Guide: [`docs/modules/messenger.md`](docs/modules/messenger.md)

## Auth

### Telegram

patchbay uses a dual-allowlist model. Every message must pass both checks.

| Chat type | Check |
|---|---|
| **Private** | `user_id ∈ allowed_user_ids` |
| **Group** | `group_id ∈ allowed_group_ids` AND `user_id ∈ allowed_user_ids` |

- **`allowed_user_ids`** — Telegram user IDs that may talk to the bot. At least one required.
- **`allowed_group_ids`** — Telegram group IDs where the bot may operate. Default `[]` = no groups.
- **`group_mention_only`** — When `true`, the bot only responds in groups when @mentioned or replied to.

All three are **hot-reloadable** — edit `config.json` and changes take effect within seconds.

> **Privacy Mode:** Telegram bots have Privacy Mode enabled by default and only see `/commands` in groups. To let the bot see all messages, make it a **group admin** or disable Privacy Mode via BotFather (`/setprivacy` → Disable). If changed after joining, remove and re-add the bot.

**Group management:** When the bot is added to a group not in `allowed_group_ids`, it warns and auto-leaves. Use `/where` to see tracked groups and their IDs.

**Channel allowlist:** Telegram channels are tracked separately via `allowed_channel_ids`. Unauthorized channels are announced and auto-left on join/audit just like unauthorized groups.

> **Tip — adding a group for the first time:**
> 1. Create a Telegram group, enable topics if you want isolated chats
> 2. Add the bot and make it **admin** (required for full message access)
> 3. Send a message mentioning `@your_bot` — the bot won't respond yet
> 4. In your private chat with the bot, run `/where` — you'll see the group listed under "Rejected" with its ID
> 5. Tell the bot: *"Add this as an allowed group in the config"* — it updates `config.json` for you
> 6. Run `/restart` — the bot now responds in the group

### Matrix

Matrix auth uses room and user allowlists in the `matrix` config block:

- **`allowed_rooms`** — Room IDs or aliases where the bot may operate.
- **`allowed_users`** — Matrix user IDs allowed to interact with the bot.

`group_mention_only` nuance on Matrix:

- In non-DM rooms, when `group_mention_only=true`, the bot requires @mention/reply and bypasses `allowed_users` checks for those group messages.
- Room-level filtering (`allowed_rooms`) still applies.

The bot logs in with password on first start, then persists `access_token` and `device_id` for subsequent runs. E2EE is supported via `matrix-nio[e2e]`.

### Slack

Slack runs through **Socket Mode**, so patchbay does not need a public webhook URL.

Create a Slack app, then configure these permissions before installing it to your workspace.

**Bot token scopes**

| Scope | Why patchbay needs it |
|---|---|
| `chat:write` | send replies as the bot |
| `app_mentions:read` | detect `@bot` in channels |
| `channels:history` | read public-channel messages and thread history |
| `channels:read` | resolve public channel metadata |
| `groups:history` | read private-channel messages and thread history |
| `im:history` | read direct messages |
| `im:read` | access DM metadata |
| `im:write` | open/manage DMs |
| `users:read` | resolve user display names for thread backfill/context |
| `files:read` | download attached files |
| `files:write` | upload generated files |

**Optional bot token scope**

| Scope | When to add it |
|---|---|
| `groups:read` | if you want private-channel metadata lookups beyond history access |

**App-level token scope**

| Scope | Why patchbay needs it |
|---|---|
| `connections:write` | required for Socket Mode (`xapp-...`) |

**Event subscriptions**

| Event | Required | Purpose |
|---|---|---|
| `message.im` | yes | direct messages |
| `message.channels` | yes | public-channel messages |
| `message.groups` | recommended | private-channel messages |
| `app_mention` | yes | mention handling in channels |

Also enable **App Home → Messages Tab** so users can DM the bot, then **Install App to Workspace** and copy:

- **Bot User OAuth Token** → `slack.bot_token` (`xoxb-...`)
- **App-Level Token** → `slack.app_token` (`xapp-...`)

If you change scopes or subscribed events later, **reinstall the Slack app** so the new permissions take effect.

patchbay's Slack allowlist lives in the `slack` config block:

- **`allowed_users`** — Slack member IDs allowed to use the bot
- **`allowed_channels`** — Slack channel IDs where the bot may respond
- **`group_mention_only`** — when `true`, channel conversations start on `@bot` and continue in the activated thread

After setup, invite the app into each target channel. Full step-by-step setup is in [`docs/installation.md#slack-setup`](docs/installation.md#slack-setup).

## Language

patchbay's UI (commands, status messages, onboarding) is available in multiple languages:

| Code | Language |
|---|---|
| `en` | English (default) |
| `de` | Deutsch |
| `nl` | Nederlands |
| `fr` | Français |
| `ru` | Русский |
| `es` | Español |
| `pt` | Português |

Set the language in `config.json`:

```json
{"language": "de"}
```

This is **hot-reloadable** — change the language without restarting the bot.

## Commands

| Command | Description |
|---|---|
| `/model` | Interactive model/provider selector |
| `/effort` | Reasoning effort for the current chat/topic (Claude & Codex) |
| `/account` | Switch the Claude credential store (see `claude_accounts` in docs/config.md) |
| `/persona` | Choose which Claude Code agent governs this chat/topic |
| `/plugins` | Choose which plugins load for this chat/topic |
| `/skills` | Browse available skills by plugin; tap one to copy its command |
| `/clear` | Archive the handoff, then start a completely fresh session in this topic |
| `/compact` | Write a handoff, then compact the session so the thread survives |
| `/handoff` | Show this conversation's handoff |
| `/folder` | Choose the project folder this conversation works in |
| `/consult` | Schedule for the disposable Consult topic |
| `/settings` | Values you can change from the chat instead of on the host — currently the Gemini API key that pays for handoff write-ups, verified against Google before it is stored |
| `/stop` | Stop current message and discard queued messages |
| `/interrupt` | Interrupt current message, queued messages continue |
| `/stop_all` | Kill everything — all messages, sessions, all agents |
| `/status` | Session/provider/auth status |
| `/memory` | Show persistent memory |
| `/session <prompt>` | Start a named session |
| `/named` | View/manage named sessions |
| `/cron` | Interactive cron management |
| `/files` | Browse `~/.phoenix-patchbay/` and your configured `project_roots`; download, upload, rename, create, delete, and pull/push git. `/showfiles` still works as an alias |
| `/menu` | Show or hide a persistent keyboard of the commands used most often |
| `/diagnose` | Runtime diagnostics |
| `/upgrade` | Check/apply updates |
| `/agents` | Multi-agent status |
| `/agent_commands` | Multi-agent command reference |
| `/agent_start <name>` | Start a sub-agent |
| `/agent_stop <name>` | Stop a sub-agent |
| `/agent_restart <name>` | Restart a sub-agent |
| `/help` | Command reference, grouped by what it is for |
| `/where` | Show tracked chats/groups |
| `/leave <id>` | Manually leave a group |
| `/restart` | Restart the bot process |
| `/info` | Version + links |

`/clear` archives the handoff and starts a genuinely fresh session in the topic you are
in. There is deliberately no way to reset *another* topic's session: `/new @topicname`
used to do that, and a command that reaches into a conversation you are not in is the
isolation this project exists to provide, undone by a convenience.

On Slack, these same commands also work as normal message commands (for example `help`, `status`, or `model`) even though patchbay does not register native Slack slash commands.

## Common CLI commands

```bash
patchbay                  # Start bot (auto-onboarding if needed)
patchbay onboarding       # Re-run setup wizard
patchbay reset            # Full reset + onboarding
patchbay stop             # Stop bot
patchbay restart          # Restart bot
patchbay upgrade          # Upgrade and restart
patchbay status           # Runtime status
patchbay help             # CLI overview
patchbay uninstall        # Remove bot + workspace

patchbay service install  # Install as background service
patchbay service status   # Show service status
patchbay service start    # Start service
patchbay service stop     # Stop service
patchbay service logs     # View service logs
patchbay service uninstall

patchbay docker enable    # Enable Docker sandbox
patchbay docker rebuild   # Rebuild sandbox container
patchbay docker mount /p  # Add host mount
patchbay docker extras    # List optional sandbox packages

patchbay agents list      # List configured sub-agents
patchbay agents add NAME  # Add a sub-agent
patchbay agents remove NAME

patchbay api enable       # Enable WebSocket API (beta)
patchbay api disable      # Disable WebSocket API

patchbay install matrix   # Install Matrix transport extra
patchbay install api      # Install API/PyNaCl extra
```

`patchbay agents add` currently scaffolds Telegram sub-agents interactively. Matrix
sub-agents are supported at runtime, but you configure them via `agents.json` or
the bundled agent tool scripts.

## Workspace layout

```text
~/.phoenix-patchbay/
  config/config.json                 # Bot configuration
  sessions.json                      # Chat session state
  named_sessions.json                # Named sessions
  cron_jobs.json                     # Scheduled jobs
  webhooks.json                      # Webhook definitions
  agents.json                        # Sub-agent registry (optional)
  SHAREDMEMORY.md                    # Shared knowledge across all agents
  CLAUDE.md / AGENTS.md / GEMINI.md  # Rule files
  logs/agent.log
  workspace/
    memory_system/MAINMEMORY.md      # Persistent memory (global facts only)
    cron_tasks/ skills/ tools/       # Scripts and tools
    telegram_files/ matrix_files/    # Media files (per transport)
    api_files/                       # Uploaded/downloadable API files
    output_to_user/                  # Generated deliverables
  agents/<name>/                     # Sub-agent workspaces (isolated)
```

Full config reference: [`docs/config.md`](docs/config.md) — full example with all options: [`config.example.json`](config.example.json)

## Documentation

| Doc | Content |
|---|---|
| [System Overview](docs/system_overview.md) | End-to-end runtime overview |
| [Developer Quickstart](docs/developer_quickstart.md) | Quickest path for contributors |
| [Architecture](docs/architecture.md) | Startup, routing, streaming, callbacks |
| [Configuration](docs/config.md) | Config schema and merge behavior |
| [Matrix Setup](docs/matrix-setup.md) | Adding Matrix as transport |
| [Automation](docs/automation.md) | Cron, webhooks, heartbeat setup |
| [Service Management](docs/modules/service_management.md) | systemd, launchd, Task Scheduler backends |
| [Module docs](docs/modules/) | Per-module deep dives |

## Why patchbay?

Other projects manipulate SDKs or patch CLIs and risk violating provider terms of service. patchbay simply runs the official CLI binaries as subprocesses — nothing more.

- Official CLIs only (`claude`, `codex`, `gemini`, `agy`, `grok`)
- Rule files are plain Markdown (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md` — `AGENTS.md` is shared by Codex and Grok)
- Memory is one Markdown file per agent
- All state is JSON — no database, no external services

## Compared to Hermes Agent

[Hermes Agent](https://github.com/nousresearch/hermes-agent) (Nous Research, MIT) is the
project patchbay gets compared to most, and the comparison is worth making properly,
because the two are not the same kind of thing.

**Hermes is an agent. Patchbay is a machine that runs agents.**

Hermes brings its own agent loop and its own model layer — point it at Nous Portal,
OpenRouter, OpenAI or a custom endpoint and it reasons, calls tools, and writes its own
skills. Patchbay has neither: it runs the official CLIs (`claude`, `codex`, `gemini`,
`agy`, `grok`) as subprocesses, so the reasoning is whatever your subscription already
pays for, and the surface is a chat window where the terminal would be. Most of what
follows is a consequence of that one difference.

### Side by side

| | Phoenix Patchbay | Hermes Agent |
|---|---|---|
| **What it is** | Runtime that fronts agents you already have | A complete agent, loop included |
| **Who reasons** | The CLI's model, unchanged | Hermes, against your chosen endpoint |
| **Cost model** | Your existing CLI subscription — no API key, no per-token bill | Per-token against an API key |
| **Switching providers** | Per topic, mid-project, no migration | One agent, one config |
| **Surfaces** | Telegram, Matrix, Slack | 20+ (Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Teams, …) |
| **Where work runs** | One always-on box you own | Local, Docker, SSH, Daytona, Singularity, Modal, Vercel Sandbox |
| **Unit of isolation** | One topic = one session = one project folder | One agent; sub-agents as short-lived workers |
| **Memory the model sees** | Handoff, injected at session start and again after every compaction | `MEMORY.md` / `USER.md`, snapshotted into the system prompt at session start |
| **Long-term recall** | Append-only history per conversation, plus archives and transcripts — searched, not indexed | SQLite FTS5 across sessions, with LLM summarisation |
| **Improvement loop** | Per conversation, through its handoff | Self-authored, self-revising skills (agentskills.io standard) |
| **State** | JSON and Markdown, no database | Markdown plus SQLite |
| **MCP** | Whatever the underlying CLI supports | Built in |

### Behaviour, where it actually differs

**Memory freshness.** Closer than it looks. Both inject curated memory at session start;
between boundaries, both rely on the conversation itself. Hermes's mid-session memory
writes are durable immediately but do not change the running prompt until it is rebuilt.
Patchbay's handoff is written up as work piles up and re-injected after every compaction,
automatic or `/compact` — the moment the model has just lost its working context and
needs it most. What patchbay does send on every turn is one line pointing at the
conversation's history file, so the way back to a dropped detail is never out of reach.

**Guaranteed versus retrieved.** A handoff is injected text: if a constraint is written
down, the model has read it. Search-backed recall is probabilistic — the fact can be in
the store and still never surface for the query the agent happened to ask. For rules that
must never be broken, injection is the stronger guarantee. For "what did we try in July",
search is the only thing that scales.

**Precision over time.** Both keep everything; they differ in how it is found again. The
handoff itself is lossy by design, so every version of it is appended to
`handoffs/<conversation>.history.md` before it is overwritten — plain Markdown, newest
last, and the agent is given the path in the same breath as the handoff. Retrieval is a
search over a file rather than a query against an index: adequate at the scale one
conversation reaches, and it stays greppable by anything, corrupts one line at a time
rather than one database at a time, and needs no schema. Hermes's SQLite store scales
further and ranks better. If a single history ever outgrows `grep`, indexing it is an
additive change — the store is already on disk, in the open.

**Isolation.** Patchbay isolates by path: one topic, one folder, one handoff file, one
session. Nothing shared unless it is deliberately placed in `SHAREDMEMORY.md` or
`workspace/memory_system/MAINMEMORY.md`. Hermes isolates one agent's memory from another
inside its own store, and leans on short-lived sub-agents to keep contexts focused.

**Auditability.** Patchbay's memory is Markdown in the project folder — readable on a
phone, diffable in git, fixable by editing a line. A database is queryable but not
reviewable; you cannot skim a schema change the way you skim a diff.

**Learning.** Hermes distils a finished task into a reusable skill and rewrites that skill
when it finds a better approach. Patchbay has no equivalent, deliberately: improvement is
scoped to the conversation that earned it, which is the same principle behind removing
background task delegation. Skills that leak across projects are a feature until the day
one of them is wrong everywhere at once.

### Which to reach for

**Patchbay fits when** the work is real projects on real repositories, you already pay for
Claude Code / Codex / Gemini and would rather not pay twice, you want per-topic isolation
strong enough that five projects can share one chat window without contaminating each
other, and you want every artefact — memory included — to be a file you can read.

**Hermes fits when** you want one agent that accumulates capability across everything you
do, you would rather bring your own endpoint (including local or open-weight models) than
be bound to vendor CLIs, you need a surface patchbay does not speak, or you need the work
to run somewhere ephemeral — a serverless sandbox that hibernates when idle.

They are not mutually exclusive. Hermes is an agent with a CLI, and patchbay's job is
running agent CLIs.

*Hermes details here reflect its documentation as of September 2026; it moves quickly.*

## Disclaimer

patchbay runs official provider CLIs and does not impersonate provider clients. Validate your own compliance requirements before unattended automation.

- [Anthropic Terms](https://www.anthropic.com/policies/terms)
- [OpenAI Terms](https://openai.com/policies/terms-of-use)
- [Google Terms](https://policies.google.com/terms)

## Contributing

```bash
git clone https://github.com/ali-rajabpour/PhoenixPatchbay.git
cd PhoenixPatchbay
uv sync --extra dev
```

Run checks with [just](https://github.com/casey/just):

```bash
just check   # linters + type checks (parallel)
just test    # test suite
just fix     # auto-fix formatting and lint issues
```

Or directly with uv:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy phoenix_patchbay
```

Zero warnings, zero errors.

## License

[MIT](LICENSE)

## Author

**Ali Rajabpour Sanati**

- Website: <https://Rajabpour.com>
- GitHub: <https://github.com/ali-rajabpour>
- Email: <ali.poursanati@gmail.com>

Upstream project: [ductor](https://github.com/PleasePrompto/ductor) by PleasePrompto (MIT).
