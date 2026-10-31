#!/bin/bash
# Install runtime requirements for Debian/Ubuntu KDE Plasma.
set -euo pipefail

PACKAGES=(
    python3-pyside6.qtwidgets
    plasma-integration
    polkitd pkexec
    xinput network-manager
    wev x11-utils
    libkf6config-bin libkf6service-bin
    kmod
)

if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found. This installer targets Debian/Ubuntu KDE Plasma." >&2
    exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
    APT=(apt-get)
else
    command -v sudo >/dev/null 2>&1 || {
        echo "Run this installer as root or install sudo first." >&2
        exit 1
    }
    APT=(sudo apt-get)
fi

echo "Updating apt package lists..."
"${APT[@]}" update
echo "Installing dependencies: ${PACKAGES[*]}"
"${APT[@]}" install -y "${PACKAGES[@]}"
echo "Dependencies installed."
