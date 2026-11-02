#!/usr/bin/env bash
# vishvakarma's installer: links ~/.local/bin/vishvakarma and the login unit, then
# gives every agent the skills and tools. No root. From a checkout (kosha's
# copy) it installs that; otherwise it clones its newest release first:
#
#   curl -fsSL https://raw.githubusercontent.com/Theyashsawarkar/vishvakarma/main/install.sh | bash
set -euo pipefail
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null ||
  { echo "vishvakarma needs Python 3.11 or newer" >&2; exit 1; }
here=$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || true)
if [ -n "$here" ] && [ -f "$here/bin/vishvakarma" ]; then
  src=$here
else
  command -v git >/dev/null || { echo "vishvakarma needs git" >&2; exit 1; }
  src="${XDG_DATA_HOME:-$HOME/.local/share}/vishvakarma"
  if [ -d "$src/.git" ]; then
    git -C "$src" fetch -q --tags origin
  else
    git clone -q https://github.com/Theyashsawarkar/vishvakarma "$src"
  fi
  latest=$(git -C "$src" tag -l 'v*' --sort=-v:refname | head -1)
  [ -n "$latest" ] && git -C "$src" -c advice.detachedHead=false checkout -q "$latest"
fi
mkdir -p "$HOME/.local/bin"
ln -sfn "$src/bin/vishvakarma" "$HOME/.local/bin/vishvakarma"
# Synced again at every login: new agents, new vesha profiles, new skills.
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$units"
ln -sfn "$src/systemd/vishvakarma.service" "$units/vishvakarma.service"
systemctl --user daemon-reload 2>/dev/null || true
# In the app launcher: vishvakarma ui, with its icon.
share="${XDG_DATA_HOME:-$HOME/.local/share}"
mkdir -p "$share/applications" "$share/icons/hicolor/scalable/apps"
sed "s|@BIN@|$HOME/.local/bin/vishvakarma|" "$src/assets/vishvakarma.desktop" > "$share/applications/vishvakarma.desktop"
cp "$src/assets/logo.svg" "$share/icons/hicolor/scalable/apps/vishvakarma.svg"
"$src/bin/vishvakarma" sync
echo "vishvakarma installed: $HOME/.local/bin/vishvakarma"
echo "to sync at every login: systemctl --user enable vishvakarma (Vayu starts it for you)"
