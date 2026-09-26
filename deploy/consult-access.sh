#!/bin/bash
# Let the Consult account authenticate the CLI. Safe to run on every start.
#
# The Consult topic runs the CLI as the unix account `consult` (see the Dockerfile),
# which cannot read the bot's ~/.claude. It authenticates through a symlink to the
# bot's credentials, and that link lives in the image layer, not the volume: it is
# gone after every container recreate. The permissions are on the volume, but a
# token refresh that rewrites the file resets them. So this runs at every start
# rather than once by hand.
#
# Without it Consult fails with "not logged in". Never fatal: the bot works
# without Consult, so a failure here is reported and the start continues.

set -uo pipefail

ACCOUNT=consult
id "$ACCOUNT" >/dev/null 2>&1 || exit 0 # no such account: nothing to do

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CREDS="$CLAUDE_DIR/.credentials.json"
ACCOUNT_HOME="$(getent passwd "$ACCOUNT" | cut -d: -f6)"

[ -f "$CREDS" ] || exit 0 # not logged in yet; the entrypoint calls us again after login

# 0710: the account can reach a path it already knows but cannot list the
# directory, so session files (unpredictable names) stay private.
# The bot is in the account's group, so no sudo is needed for these.
chgrp "$ACCOUNT" "$CLAUDE_DIR" "$CREDS" || echo "consult-access: chgrp failed"
chmod 710 "$CLAUDE_DIR"
# Group-writable: the CLI rewrites this file when the OAuth token refreshes.
chmod 660 "$CREDS"

# The account's own config dir keeps its sessions apart from the bot's; only the
# credentials are shared, by symlink, so a refresh is visible to both.
sudo -n -u "$ACCOUNT" sh -c "mkdir -p '$ACCOUNT_HOME/.claude' && chmod 700 '$ACCOUNT_HOME/.claude' \
    && ln -sfn '$CREDS' '$ACCOUNT_HOME/.claude/.credentials.json'" \
    || echo "consult-access: could not link credentials for $ACCOUNT"
