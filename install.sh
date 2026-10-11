#!/bin/sh
# Installs the udev rule (needs sudo), a `akkoctl` command and a menu entry.
set -e
DIR="$(dirname "$(readlink -f "$0")")"

echo "Installing udev rule (sudo needed once)..."
sudo install -m 644 "$DIR/70-akko-via.rules" /etc/udev/rules.d/70-akko-via.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sf "$DIR/akkoctl-run" "$HOME/.local/bin/akkoctl"
cat > "$HOME/.local/share/applications/akkoctl.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Akko Keyboard Control
Comment=Lighting, keymap and macros for the Akko 5075B Plus-S
Exec=$DIR/akkoctl-run gui
Icon=input-keyboard
Categories=Settings;HardwareSettings;
DESKTOP

echo "Done. Run 'akkoctl gui' or open 'Akko Keyboard Control' from the app menu."
echo "If 'akkoctl' isn't found, make sure ~/.local/bin is on your PATH."
