#!/bin/sh
# Installs the udev rule (needs sudo), a `viactl` command and a menu entry.
set -e
DIR="$(dirname "$(readlink -f "$0")")"

echo "Installing udev rule (sudo needed once)..."
sudo install -m 644 "$DIR/70-viactl.rules" /etc/udev/rules.d/70-viactl.rules
# Rule file from when this project was called akkoctl
sudo rm -f /etc/udev/rules.d/70-akko-via.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sf "$DIR/viactl-run" "$HOME/.local/bin/viactl"
# Old command name, kept for now so scripts using it keep working
ln -sf "$DIR/viactl-run" "$HOME/.local/bin/akkoctl"
rm -f "$HOME/.local/share/applications/akkoctl.desktop"
cat > "$HOME/.local/share/applications/viactl.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=VIA Keyboard Control
Comment=Lighting, keymap and macros for VIA keyboards
Exec=$DIR/viactl-run gui
Icon=input-keyboard
Categories=Settings;HardwareSettings;
DESKTOP

echo "Done. Run 'viactl gui' or open 'VIA Keyboard Control' from the app menu."
echo "If 'viactl' isn't found, make sure ~/.local/bin is on your PATH."
