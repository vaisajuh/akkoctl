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
