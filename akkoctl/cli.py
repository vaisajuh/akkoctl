"""Command-line interface: `akkoctl <command> ...`"""

import argparse
import sys

from . import macros, via
from .keycodes import Keycodes
from .layout import LAYOUTS, layout_for


def open_keyboard(args):
    if args.demo:
        from .fake import fake_keyboard
        return fake_keyboard()
    return via.Keyboard.open(args.device)


def zone(args):
    """(channel, effect names, effects without color) for --side or keys."""
    return via.ZONES["side" if getattr(args, "side", False) else "keys"]


def parse_effect(text, effects):
    if text.isdigit():
        n = int(text)
    else:
        names = [e.lower().replace(" ", "") for e in effects]
        key = text.lower().replace(" ", "").replace("-", "").replace("_", "")
        if key not in names:
            raise ValueError(f"unknown effect '{text}' (see `akkoctl effects`)")
        n = names.index(key)
    if not 0 <= n < len(effects):
        raise ValueError(f"effect must be 0-{len(effects) - 1}")
    return n


def percent_or_byte(text):
    """'50%' -> 128, '128' -> 128."""
    if text.endswith("%"):
        return via.clamp(round(float(text[:-1]) * 255 / 100))
    return via.clamp(int(text))


def cmd_list(args):
    devices = via.find_devices()
    if not devices:
        print("No VIA keyboards found.")
    for d in devices:
        print(f"{d['path']}  {d['vid']:04x}:{d['pid']:04x}  {d['name']}")


def cmd_info(kb, args):
    print(f"VIA protocol : {kb.protocol}")
    for label, fn in (("Firmware     ", kb.get_firmware_version),
                      ("Uptime       ", lambda: f"{kb.get_uptime_ms() / 1000:.0f} s"),
                      ("Layers       ", kb.get_layer_count),
                      ("Macros       ", kb.get_macro_count)):
        try:
            value = fn()
            if label.startswith("Firmware"):
                value = f"0x{value:08X}"
            print(f"{label}: {value}")
        except via.ViaError as e:
            print(f"{label}: ({e})")
    cmd_status(kb, args)


def cmd_status(kb, args):
    side = getattr(args, "side", None)  # None: show both zones
    zones = ["keys", "side"] if side is None else ["side" if side else "keys"]
    for name in zones:
        channel, effects, _ = via.ZONES[name]
        try:
            s = kb.get_lighting(channel)
        except via.ViaError as e:
            print(f"[{name}] ({e})")
            continue
        hue, sat = s["color"]
        r, g, b = via.hue_sat_to_rgb(hue, sat)
        effect = effects[s["effect"]] if s["effect"] < len(effects) else "?"
        print(f"[{'Key backlight' if name == 'keys' else 'Sidelights'}]")
        print(f"Effect       : {s['effect']} ({effect})")
        print(f"Brightness   : {s['brightness']} ({s['brightness'] * 100 // 255}%)")
        print(f"Speed        : {s['speed']} ({s['speed'] * 100 // 255}%)")
        print(f"Color        : #{r:02x}{g:02x}{b:02x} (hue {hue}, sat {sat})")


def cmd_effects(args):
    _, effects, without_color = zone(args)
    for i, name in enumerate(effects):
        note = "  (own colors)" if i and i in without_color else ""
        print(f"{i:3}  {name}{note}")


def cmd_set(kb, args):
    channel, effects, _ = zone(args)
    changed = False
    if args.effect is not None:
        kb.set_effect(parse_effect(args.effect, effects), channel)
        changed = True
    if args.brightness is not None:
        kb.set_brightness(args.brightness, channel)
        changed = True
    if args.speed is not None:
        kb.set_speed(args.speed, channel)
        changed = True
    if args.color is not None:
        kb.set_color(*via.parse_color(args.color), channel=channel)
        changed = True
    if args.off:
        kb.set_effect(0, channel)
        changed = True
    if not changed:
        sys.exit("Nothing to set. Try e.g.  akkoctl set --effect breathing --color red")
    if not args.temp:
        kb.save_lighting(channel)
    cmd_status(kb, args)


def cmd_keymap(kb, args):
    kc = Keycodes(kb.protocol)
    keymap = kb.get_keymap()
    keys = layout_for(kb.pid, args.layout)
    layers = [args.layer] if args.layer is not None else range(len(keymap))
    for layer in layers:
        print(f"== Layer {layer}")
        for row in range(kb.rows):
            cells = [f"{kc.name(keymap[layer][row][col]):>9}"
                     for (r, col, *_rest) in sorted(keys, key=lambda k: k[2]) if r == row]
            print(" ".join(cells))


def cmd_remap(kb, args):
    kc = Keycodes(kb.protocol)
    code = kc.parse(args.keycode)
    old = kb.get_keycode(args.layer, args.row, args.col)
    kb.set_keycode(args.layer, args.row, args.col, code)
    print(f"Layer {args.layer} key ({args.row},{args.col}): "
          f"{kc.name(old)} -> {kc.name(code)}")


def cmd_macro(kb, args):
    kc = Keycodes(kb.protocol)
    count = kb.get_macro_count()
    current = macros.decode(kb.get_macro_buffer(), count, kc)
    if args.index is None:
        for i, text in enumerate(current):
            print(f"M{i:<3} {text!r}" if text else f"M{i:<3} (empty)")
        print("\nAssign macro N to a key with: akkoctl remap LAYER ROW COL MN")
        return
    if not 0 <= args.index < count:
        sys.exit(f"Macro index must be 0-{count - 1}")
    current[args.index] = args.text
    kb.set_macro_buffer(macros.encode(current, kc))
    print(f"M{args.index} = {args.text!r}")


def cmd_reset(kb, args):
    if not args.yes:
        sys.exit(f"This will reset {args.what}. Re-run with --yes to confirm.")
    {"keymap": kb.reset_keymap, "macros": kb.reset_macros,
     "everything": kb.factory_reset}[args.what]()
    print(f"Reset {args.what}. Unplug and replug the keyboard if it looks odd.")


def build_parser():
    p = argparse.ArgumentParser(
        prog="akkoctl",
        description="Control lighting, keymap and macros on an Akko 5075B "
                    "Plus-S (or any VIA keyboard). Use it with the keyboard "
                    "connected by USB in wired mode.")
    p.add_argument("--device", help="hidraw path (default: auto-detect)")
    p.add_argument("--demo", action="store_true",
                   help="use an emulated keyboard (for trying things out)")
    p.add_argument("--layout", choices=sorted(LAYOUTS),
                   help="physical layout (default: detected from the USB id)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list connected VIA keyboards")
    sub.add_parser("info", help="show firmware info and current lighting")
    s = sub.add_parser("status", help="show current lighting")
    s.add_argument("--side", action="store_true", help="sidelights only")
    s.add_argument("--keys", dest="side", action="store_false", help="key backlight only")
    s.set_defaults(side=None)
    s = sub.add_parser("effects", help="list lighting effects")
    s.add_argument("--side", action="store_true", help="sidelight effects")

    s = sub.add_parser("set", help="change lighting",
                       epilog="Examples:\n  akkoctl set --effect breathing --color '#00aaff'\n"
                              "  akkoctl set -b 40%% -s 80%%\n  akkoctl set --off\n"
                              "  akkoctl set --side --effect 'rainbow swirl 3'",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument("--side", action="store_true",
                   help="change the sidelights instead of the key backlight")
    s.add_argument("-e", "--effect", help="effect name or number")
    s.add_argument("-b", "--brightness", type=percent_or_byte, help="0-255 or N%%")
    s.add_argument("-s", "--speed", type=percent_or_byte, help="0-255 or N%%")
    s.add_argument("-c", "--color", help="#RRGGBB, a color name, or hsv:H,S")
    s.add_argument("--off", action="store_true", help="turn lighting off")
    s.add_argument("--temp", action="store_true",
                   help="don't save to the keyboard (lost on unplug)")

    s = sub.add_parser("keymap", help="print the keymap")
    s.add_argument("--layer", type=int)

    s = sub.add_parser("remap", help="change what a key does",
                       epilog="KEYCODE can be KC_A, ESC, MO(1), LCTL(KC_C), "
                              "LT(1,KC_SPC), M0 (macro), BT_DEV1, or hex like 0x0004.\n"
                              "Find ROW/COL with `akkoctl gui` (hover a key) "
                              "or `akkoctl keymap`.",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument("layer", type=int)
    s.add_argument("row", type=int)
    s.add_argument("col", type=int)
    s.add_argument("keycode")

    s = sub.add_parser("macro", help="list macros, or set one",
                       epilog="TEXT syntax: plain text, {KC_ENTER} tap, "
                              "{+KC_LCTL}/{-KC_LCTL} hold/release, {200ms} delay.")
    s.add_argument("index", type=int, nargs="?")
    s.add_argument("text", nargs="?", default="")

    s = sub.add_parser("reset", help="reset keymap, macros, or everything")
    s.add_argument("what", choices=["keymap", "macros", "everything"])
    s.add_argument("--yes", action="store_true")

    sub.add_parser("gui", help="open the graphical app")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "effects":
        return cmd_effects(args)
    if args.cmd == "gui":
        from .gui import main as gui_main
        return gui_main(demo=args.demo, device=args.device, layout=args.layout)
    handlers = {"info": cmd_info, "status": cmd_status, "set": cmd_set,
                "keymap": cmd_keymap, "remap": cmd_remap, "macro": cmd_macro,
                "reset": cmd_reset}
    try:
        kb = open_keyboard(args)
        try:
            handlers[args.cmd](kb, args)
        finally:
            kb.close()
    except (via.ViaError, ValueError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
