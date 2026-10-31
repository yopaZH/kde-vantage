#!/bin/bash
# Installs Vantage's dependencies. This fork targets Arch Linux/KDE Plasma.
set -euo pipefail

PACKAGES=(python-pyside6 plasma-integration polkit xorg-xinput networkmanager wev xorg-xev)

command -v pacman &>/dev/null || {
    echo "pacman not found - this installer targets Arch Linux." >&2
    exit 1
}

echo "Installing dependencies: ${PACKAGES[*]}"
pacman -Qi "${PACKAGES[@]}" &>/dev/null || sudo pacman -S --needed "${PACKAGES[@]}"

echo "Dependencies installed."
