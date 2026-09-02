FROM python:3.13-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    NODE_MAJOR=22

# Base toolchain for an agent workspace: VCS, HTTP, search, build tools.
# ripgrep is what Claude Code shells out to for search.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg git openssh-client \
        ripgrep jq less unzip zip procps tini iproute2 sudo tmux nano \
        build-essential \
        socat \
    && rm -rf /var/lib/apt/lists/*

# Node from NodeSource: Debian trixie ships 20.x, but Claude Code declares
# engines >=22 and warns on every npm operation otherwise.
RUN curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" -o /tmp/nodesource.sh \
    && bash /tmp/nodesource.sh \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* /tmp/nodesource.sh

# Chromium for agent-browser. Taken from Debian rather than letting the tool
# fetch its own, so it gets security updates like everything else here.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_PATH=/usr/bin/chromium \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    PLAYWRIGHT_BROWSERS_PATH=/home/patchbay/.cache/ms-playwright

# rtk — the CLI proxy the PreToolUse hook shells out to on every tool call.
# NOTE: the `rtk` package on npm is an unrelated release-management tool
# (cliffano/rtk). The one wanted here is rtk-ai/rtk, shipped as a .deb.
ARG RTK_VERSION=0.45.0
RUN curl -fsSL -o /tmp/rtk.deb \
        "https://github.com/rtk-ai/rtk/releases/download/v${RTK_VERSION}/rtk_${RTK_VERSION}-1_amd64.deb" \
    && dpkg -i /tmp/rtk.deb \
    && rm /tmp/rtk.deb \
    && rtk --version

# github-mcp-server: the local setup points at a Homebrew path, so the Linux
# build is fetched here instead of trying to port the macOS binary.
ARG GITHUB_MCP_VERSION=1.10.1
RUN curl -fsSL -o /tmp/ghmcp.tar.gz \
        "https://github.com/github/github-mcp-server/releases/download/v${GITHUB_MCP_VERSION}/github-mcp-server_Linux_x86_64.tar.gz" \
    && tar -xzf /tmp/ghmcp.tar.gz -C /usr/local/bin github-mcp-server \
    && rm /tmp/ghmcp.tar.gz \
    && chmod +x /usr/local/bin/github-mcp-server \
    && github-mcp-server --version

# GitHub CLI, for PRs, issues and review replies. Authenticates from GH_TOKEN,
# which is supplied at runtime rather than baked into the image.
ARG GH_VERSION=2.65.0
RUN curl -fsSL -o /tmp/gh.tar.gz \
        "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" \
    && tar -xzf /tmp/gh.tar.gz -C /tmp \
    && install -m 0755 "/tmp/gh_${GH_VERSION}_linux_amd64/bin/gh" /usr/local/bin/gh \
    && rm -rf /tmp/gh.tar.gz "/tmp/gh_${GH_VERSION}_linux_amd64" \
    && gh --version | head -1

# Global npm installs go to a dedicated prefix owned by the runtime user, so
# Claude Code can self-update in place without anything being writable in /usr.
# (NodeSource sets the prefix to /usr, where "make the prefix writable" would
# mean handing over every system binary.)
ENV NPM_CONFIG_PREFIX=/opt/npm-global \
    PATH=/opt/npm-global/bin:$PATH
RUN mkdir -p /opt/npm-global \
    && printf 'export PATH=/opt/npm-global/bin:$PATH\n' > /etc/profile.d/npm-global.sh

# Claude Code plus the CLI-side tools the ported workspace expects.
ARG CLAUDE_VERSION=latest
ARG CONTEXT_MODE_VERSION=latest
ARG AGENT_BROWSER_VERSION=latest
RUN npm install -g \
        "@anthropic-ai/claude-code@${CLAUDE_VERSION}" \
        "context-mode@${CONTEXT_MODE_VERSION}" \
        "agent-browser@${AGENT_BROWSER_VERSION}" \
    && npm cache clean --force \
    && claude --version

# Phoenix Patchbay itself. Pin PATCHBAY_REF to a commit for a reproducible
# build; `main` tracks the latest release.
ARG PATCHBAY_REPO=https://github.com/ali-rajabpour/PhoenixPatchbay
ARG PATCHBAY_REF=main
# No `|| true` here on purpose: a failed install would otherwise produce an
# image whose only symptom is `patchbay: not found` at runtime, long after the
# build reported success.
RUN pip install "phoenix-patchbay[api] @ git+${PATCHBAY_REPO}@${PATCHBAY_REF}" \
    && patchbay --version

# Claude Code refuses --dangerously-skip-permissions (which patchbay's default
# permission_mode: bypassPermissions maps to) when euid is 0, so the bot cannot
# run as container-root. Run as an ordinary user and hand it passwordless sudo
# instead: the agent still installs packages, and container-root is an
# unprivileged subuid on the host anyway because the daemon is rootless.
RUN useradd --create-home --uid 1000 --shell /bin/bash patchbay \
    && echo 'patchbay ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/patchbay \
    && chmod 440 /etc/sudoers.d/patchbay

# The Consult topic runs as its own account so its isolation is enforced by
# file permissions rather than by the rule in its CLAUDE.md. `consult` is NOT
# in the patchbay group, so it cannot read the project tree (0750 patchbay:patchbay);
# `patchbay` IS in the consult group, so the bot can still browse and wipe what
# that account writes.
RUN useradd --create-home --shell /usr/sbin/nologin consult \
    && usermod -aG consult patchbay \
    && chmod 750 /home/consult

# Hand the npm prefix to the runtime user so Claude Code and its plugins can
# self-update in place, the way they do on a laptop. Updates land in the
# container layer: a rebuild resets to the pinned versions and they update
# forward again from there.
RUN chown -R patchbay:patchbay /opt/npm-global

# Consult needs its own CLI config dir so its sessions never mix with the
# project topics'. It still reads the shared credential store: the CLI has to
# authenticate, so isolation here is from other projects, not from the token.
RUN mkdir -p /home/consult/.claude \
    && chown -R consult:consult /home/consult/.claude \
    && chmod 700 /home/consult/.claude

USER patchbay
WORKDIR /home/patchbay
ENV HOME=/home/patchbay \
    CLAUDE_CONFIG_DIR=/home/patchbay/.claude

# Bare `patchbay` starts the bot. On a first start it writes
# ~/.phoenix-patchbay/config/config.json from TELEGRAM_BOT_TOKEN and
# TELEGRAM_ALLOWED_USER_IDS, because the interactive wizard needs a TTY a
# container does not have.
# Defaults a fresh home gets on its first start: Claude Code settings with the
# plugins and hooks that make a chat-driven agent affordable, and the hook
# scripts they name. Copied at runtime, never on top of an existing file.
COPY --chown=patchbay:patchbay deploy/seed /etc/patchbay/seed
COPY --chmod=0755 deploy/entrypoint.sh /usr/local/bin/patchbay-entrypoint

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/patchbay-entrypoint"]
CMD ["patchbay"]
