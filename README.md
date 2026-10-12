# akkoctl — Akko 5075B Plus-S control for Linux

Controls RGB lighting, key remapping and macros on the Akko 5075B Plus-S
(USB `342d:e4f6`) through its VIA interface. It also works with other Akko/VIA
keyboards that use QMK RGB-matrix lighting. It needs only Python 3 and, for
the GUI, GTK 3 (`python3-gi`), both already on most Linux desktops.

The keyboard must be connected **by USB cable in wired mode**. VIA control
does not work over Bluetooth or 2.4G.

## Setup (once)

```sh
./install.sh
```

This installs a udev rule so your user can access the keyboard without root
(it asks for your sudo password), adds an `akkoctl` command in
`~/.local/bin`, and adds "Akko Keyboard Control" to the app menu.
Unplug and replug the keyboard afterwards.

## GUI

```sh
akkoctl gui
```

The GUI has five tabs:

- **Backlight** / **Sidelights**: effect, brightness, speed, color and
  saturation for the per-key lighting and the side light strip. Changes apply
  live and are saved to the keyboard automatically.
- **Keymap**: click any key on any layer to remap it.
- **Macros**: edit macros M0–M15, then assign them to keys on the Keymap tab.
- **Device**: firmware info and factory reset.

## CLI

```sh
akkoctl info                                   # firmware + current lighting
akkoctl effects                                # list the 46 effects
akkoctl set --effect breathing --color '#00aaff'
akkoctl set -b 40% -s 80%                      # brightness / speed
akkoctl set --effect "solid reactive" -c red
akkoctl set --off
akkoctl set -c purple --temp                   # don't save to EEPROM

akkoctl effects --side                         # sidelight effects
akkoctl set --side --effect "rainbow swirl 3"  # any `set` option works with --side
akkoctl set --side -c '#ff0000' -b 60%
akkoctl set --side --off
akkoctl status --side

akkoctl keymap --layer 0
akkoctl remap 0 3 0 KC_LCTL                    # layer 0, row 3, col 0 (Caps) -> Ctrl
akkoctl remap 1 0 1 KC_MPLY                    # Fn+F1 -> play/pause

akkoctl macro                                  # list macros
akkoctl macro 0 'git status{KC_ENT}'
akkoctl macro 1 '{+KC_LCTL}{KC_C}{-KC_LCTL}{50ms}copied'
akkoctl remap 1 0 12 M0                        # Fn+F12 types macro 0

akkoctl reset keymap --yes                     # or: macros | everything
```

Keycodes can be written as `KC_A`, `A`, `ESC`, `MO(1)`, `TG(2)`, `LCTL(KC_C)`,
`LT(1,KC_SPC)`, `M0`, `KC_TRNS`, `KC_NO`, `BT_DEV1`…`DEV_USB`, or raw hex
`0x7E00`. Hover a key in the GUI to see its row and column.

Add `--demo` to any command to try it against an emulated keyboard.

## Troubleshooting

- **"Permission denied"**: run `./install.sh` and replug the keyboard.
- **"No VIA keyboard found" / "did not answer"**: switch the keyboard to
  wired/USB mode (see the keyboard's manual) and use a data-capable USB cable.
- **"does not support command …"**: the firmware doesn't implement that
  VIA feature. Lighting and keymap commands are separate, so the others
  still work.

Development: `python3 -m unittest -v tests/test_akkoctl.py`

## How it's built

- **Finding the keyboard.** `via.py` scans `/sys/class/hidraw/*` and reads each
  device's HID report descriptor, looking for VIA's raw-HID interface (usage
  page `0xFF60`, usage `0x61`). Akko boards (`342d`) are preferred, but any VIA
  keyboard is found the same way.
- **Talking to it.** The VIA protocol is 32-byte request packets written to
  `/dev/hidrawN`, each answered by a 32-byte reply. No libusb or hidapi is
  needed, only `os.read`/`os.write` and `select` for timeouts.
- **Lighting** uses VIA's custom-value commands (`0x07` set, `0x08` get,
  `0x09` save to EEPROM). Per-key backlight is QMK's RGB-matrix channel (3);
  the side strip answers on the rgblight channel (2). Colors are QMK hue and
  saturation, converted from/to RGB.
- **Keymap** is read in bulk with the dynamic-keymap buffer commands in
  28-byte chunks. `keycodes.py` turns 16-bit QMK keycodes into names
  (`KC_A`, `LT(1,KC_SPC)`, …) and back, taking the VIA protocol version into
  account. `layout.py` holds the physical layout the GUI draws.
- **Macros** (`macros.py`) are encoded into VIA's shared macro buffer:
  NUL-separated strings with escape codes for tap, press, release and delay.
- **Front ends:** `cli.py` (argparse) and `gui.py` (GTK 3 via PyGObject).
- **Tests** run against `fake.py`, an in-memory keyboard that speaks the same
  packet protocol, which is also what `--demo` uses.

## Related projects

Part of a small set of Linux lighting tools, all pure Python with no third-party dependencies:

- [clcr](https://github.com/vaisajuh/clcr): Lighting Control Center: one tkinter desktop app for all three devices below (bundles their drivers)
- **akkoctl** (this repo): Akko 5075B Plus-S keyboard: RGB backlight, sidelights, keymap and macros
- [caselight](https://github.com/vaisajuh/caselight): ASUS Aura USB controller: motherboard and ARGB header lighting
- [logiled](https://github.com/vaisajuh/logiled): Logitech G502 HERO mouse: lighting, DPI, polling rate and onboard mode

## License

MIT. See [LICENSE](LICENSE).
