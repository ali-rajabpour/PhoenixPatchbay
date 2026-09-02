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

exec "$@"
