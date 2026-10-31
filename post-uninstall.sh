#!/bin/bash
# Run at the start of `make uninstall` (as root, via sudo), while
# vantage-bind-key is still installed. Removes the managed key binding for
# the invoking desktop user, if one was set up.
set -uo pipefail

target_user="${SUDO_USER:-}"
if [ -z "$target_user" ] || [ "$target_user" = "root" ]; then
    echo "Note: if you bound a key with vantage-bind-key, remove it by running:"
    echo "  vantage-bind-key --unbind"
    exit 0
fi

command -v vantage-bind-key >/dev/null 2>&1 || exit 0
sudo -H -u "$target_user" vantage-bind-key --unbind 2>/dev/null || true
