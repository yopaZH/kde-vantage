#!/bin/bash
# Run at the end of `make install` (as root, via sudo). Offers to bind the
# Lenovo Smart/Vantage key right away by running vantage-bind-key as the
# invoking desktop user; safe to decline, it can always be run later.
set -uo pipefail

target_user="${SUDO_USER:-}"
if [ -z "$target_user" ] || [ "$target_user" = "root" ]; then
    echo ""
    echo "Run 'vantage-bind-key' (as your normal desktop user, no sudo) to bind your"
    echo "Lenovo Smart/Vantage key to launch Vantage."
    exit 0
fi

uid=$(id -u "$target_user" 2>/dev/null) || exit 0
runtime_dir="/run/user/$uid"
socket=$(ls "$runtime_dir" 2>/dev/null | grep -E '^wayland-[0-9]+$' | head -n1)

if [ -z "$socket" ]; then
    echo ""
    echo "Run 'vantage-bind-key' (as $target_user, no sudo) to bind your Lenovo"
    echo "Smart/Vantage key to launch Vantage."
    exit 0
fi

echo ""
read -r -p "Bind your Lenovo Smart/Vantage key to launch Vantage now? [Y/n] " reply < /dev/tty || exit 0
case "$reply" in
    ""|y|Y|yes|Yes) ;;
    *) echo "Skipped. Run 'vantage-bind-key' any time to set it up."; exit 0 ;;
esac

sudo -H -u "$target_user" \
    XDG_RUNTIME_DIR="$runtime_dir" \
    WAYLAND_DISPLAY="$socket" \
    vantage-bind-key || echo "You can try again later by running: vantage-bind-key"
