#!/bin/bash
# Seed a fresh home, then hand over to the bot.
#
# Everything here is first-run only. The volume is the source of truth once it
# has content: an operator who edits settings.json must not have it overwritten
# by the next container restart.

set -euo pipefail

SEED=/etc/patchbay/seed
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

mkdir -p "$CLAUDE_DIR/hooks"

# Claude Code's settings: plugins and the two hooks that pay for themselves.
if [ ! -f "$CLAUDE_DIR/settings.json" ] && [ -f "$SEED/claude-settings.json" ]; then
    cp "$SEED/claude-settings.json" "$CLAUDE_DIR/settings.json"
    echo "patchbay: seeded $CLAUDE_DIR/settings.json"
fi

# Hooks are copied rather than symlinked: an operator editing one should not be
# editing an image file, and a rebuild should not silently change behaviour.
for hook in "$SEED"/hooks/*; do
    [ -e "$hook" ] || continue
    target="$CLAUDE_DIR/hooks/$(basename "$hook")"
    if [ ! -f "$target" ]; then
        cp "$hook" "$target"
        chmod +x "$target"
        echo "patchbay: seeded $target"
    fi
done

# Marketplaces have to be known before enabledPlugins means anything. Failure is
# not fatal — a box with no network yet should still start and say so.
if [ ! -d "$CLAUDE_DIR/plugins/marketplaces" ] && command -v claude >/dev/null 2>&1; then
    for repo in mksglu/context-mode JuliusBrussee/caveman DietrichGebert/ponytail; do
        claude plugin marketplace add "$repo" >/dev/null 2>&1 \
            && echo "patchbay: added marketplace $repo" \
            || echo "patchbay: could not add marketplace $repo (continuing)"
    done
fi

# The bot needs a logged-in CLI, and a fresh deployment has none. Exiting here
# would restart-loop with a banner, which reads like a crash rather than the
# one remaining setup step. Hold the container up and say what to do instead;
# the moment credentials appear, start for real.
CREDS="$CLAUDE_DIR/.credentials.json"
if [ ! -f "$CREDS" ]; then
    cat <<'BANNER'

  Phoenix Patchbay is up, but no coding CLI is logged in yet.

  Run this once, in another terminal:

      docker compose exec patchbay claude

  Sign in when it asks, then leave that shell. The bot starts by itself
  within ten seconds — no restart needed.

BANNER
    while [ ! -f "$CREDS" ]; do
        sleep 10
    done
    echo "patchbay: credentials found, starting"
fi

exec "$@"
