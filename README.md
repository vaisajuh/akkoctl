# viactl: VIA keyboard control for Linux

[![Tests](https://github.com/vaisajuh/viactl/actions/workflows/tests.yml/badge.svg)](https://github.com/vaisajuh/viactl/actions/workflows/tests.yml)

Controls RGB lighting, key remapping and macros on keyboards that support
**VIA**, the open configuration protocol of QMK firmware used by Akko,
Keychron, Glorious, KBDfans and many others. It needs only Python 3 and, for
the GUI, GTK 3 (`python3-gi`), both already on most Linux desktops.

*viactl was called akkoctl until October 2026. The old name still works as a
command, and old GitHub links redirect here.*

| Keyboard | Status |
| --- | --- |
| Akko 5075B Plus-S (`342d:e4f6`) | ✅ Tested by maintainer, including Akko's sidelights and custom keys |
| Other VIA keyboards with QMK RGB-matrix lighting | 🟡 Untested: same protocol, should work |

Tried another keyboard? Please [report how it went](https://github.com/vaisajuh/viactl/issues),
so it can be added to the table. Device support grows through test reports
from people who own the hardware.

The keyboard must be connected **by USB cable in wired mode**. VIA control
does not work over Bluetooth or 2.4G.

## Setup (once)

```sh
./install.sh
```

This installs a udev rule so your user can access the keyboard without root
(it asks for your sudo password), adds a `viactl` command in
`~/.local/bin`, and adds "VIA Keyboard Control" to the app menu.
Unplug and replug the keyboard afterwards.

The udev rule covers Akko keyboards. For another brand, add a line with your
keyboard's USB vendor ID to `70-viactl.rules` (see the comment in it) and run
`./install.sh` again.

## GUI

```sh
viactl gui
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
viactl info                                   # firmware + current lighting
viactl effects                                # list the 46 effects
viactl set --effect breathing --color '#00aaff'
viactl set -b 40% -s 80%                      # brightness / speed
viactl set --effect "solid reactive" -c red
viactl set --off
viactl set -c purple --temp                   # don't save to EEPROM

viactl effects --side                         # sidelight effects
viactl set --side --effect "rainbow swirl 3"  # any `set` option works with --side
viactl set --side -c '#ff0000' -b 60%
viactl set --side --off
viactl status --side

viactl keymap --layer 0
viactl remap 0 3 0 KC_LCTL                    # layer 0, row 3, col 0 (Caps) -> Ctrl
viactl remap 1 0 1 KC_MPLY                    # Fn+F1 -> play/pause

viactl macro                                  # list macros
viactl macro 0 'git status{KC_ENT}'
viactl macro 1 '{+KC_LCTL}{KC_C}{-KC_LCTL}{50ms}copied'
viactl remap 1 0 12 M0                        # Fn+F12 types macro 0

viactl reset keymap --yes                     # or: macros | everything
```

Keycodes can be written as `KC_A`, `A`, `ESC`, `MO(1)`, `TG(2)`, `LCTL(KC_C)`,
`LT(1,KC_SPC)`, `M0`, `KC_TRNS`, `KC_NO`, `BT_DEV1`…`DEV_USB`, or raw hex
`0x7E00`. Hover a key in the GUI to see its row and column.

Add `--demo` to any command to try it against an emulated keyboard.

## Troubleshooting

- **"Permission denied"**: run `./install.sh` and replug the keyboard. Not an
  Akko? Add your vendor ID to `70-viactl.rules` first (see Setup).
- **"No VIA keyboard found" / "did not answer"**: switch the keyboard to
  wired/USB mode (see the keyboard's manual) and use a data-capable USB cable.
- **"does not support command …"**: the firmware doesn't implement that
  VIA feature. Lighting and keymap commands are separate, so the others
  still work.

Development: `python3 -m unittest -v tests/test_viactl.py`

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

## Contributing

Bug reports and pull requests are welcome.

- Report bugs and ask questions in [issues](https://github.com/vaisajuh/viactl/issues).
- Run the tests before opening a pull request: `python3 -m unittest -v tests/test_viactl.py`.
  They use an emulated device, so no hardware is needed, and they also run
  automatically on every pull request.
- Use only the Python standard library (no third-party dependencies).
- `viactl/via.py`, `viactl/fake.py` are also bundled in
  [clcr](https://github.com/vaisajuh/clcr), the Computer Lighting Control
  Center. You don't need to change clcr yourself: after your pull request is
  merged here, clcr's automatic sync opens a pull request there with the change.
  If you change functions or classes in these files, say so in your pull
  request, since clcr's GUI uses them.
- Want to add a different device or brand? See clcr's
  [CONTRIBUTING.md](https://github.com/vaisajuh/clcr/blob/main/CONTRIBUTING.md#adding-a-new-device).

## Maintainer

Maintained by **Juha Väisänen** ([@vaisajuh](https://github.com/vaisajuh)).

## Related projects

Part of a small set of Linux lighting tools, all pure Python with no third-party dependencies:

- [clcr](https://github.com/vaisajuh/clcr): Computer Lighting Control Center, one desktop app for lighting across brands and devices (bundles the drivers below)
- **viactl** (this repo): VIA/QMK keyboards (tested on Akko 5075B Plus-S): RGB backlight, sidelights, keymap and macros
- [caselight](https://github.com/vaisajuh/caselight): motherboard and case lighting (currently ASUS Aura)
- [logiled](https://github.com/vaisajuh/logiled): Logitech G502 HERO mouse: lighting, DPI, polling rate and onboard mode

## License

MIT. See [LICENSE](LICENSE).
