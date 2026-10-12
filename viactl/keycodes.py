"""QMK keycode names <-> numbers, for VIA protocol 12+ and older firmware.

Only the keycodes useful for remapping are named; anything else is shown and
accepted as hex (e.g. 0x7E05).
"""

import re

MOD_NAMES = ["CTL", "SFT", "ALT", "GUI"]

BASIC = {
    0x00: "KC_NO", 0x01: "KC_TRNS",
    0x28: "KC_ENT", 0x29: "KC_ESC", 0x2A: "KC_BSPC", 0x2B: "KC_TAB",
    0x2C: "KC_SPC", 0x2D: "KC_MINS", 0x2E: "KC_EQL", 0x2F: "KC_LBRC",
    0x30: "KC_RBRC", 0x31: "KC_BSLS", 0x32: "KC_NUHS", 0x33: "KC_SCLN",
    0x34: "KC_QUOT", 0x35: "KC_GRV", 0x36: "KC_COMM", 0x37: "KC_DOT",
    0x38: "KC_SLSH", 0x39: "KC_CAPS", 0x46: "KC_PSCR", 0x47: "KC_SCRL",
    0x48: "KC_PAUS", 0x49: "KC_INS", 0x4A: "KC_HOME", 0x4B: "KC_PGUP",
    0x4C: "KC_DEL", 0x4D: "KC_END", 0x4E: "KC_PGDN", 0x4F: "KC_RGHT",
    0x50: "KC_LEFT", 0x51: "KC_DOWN", 0x52: "KC_UP", 0x53: "KC_NUM",
    0x54: "KC_PSLS", 0x55: "KC_PAST", 0x56: "KC_PMNS", 0x57: "KC_PPLS",
    0x58: "KC_PENT", 0x62: "KC_P0", 0x63: "KC_PDOT", 0x64: "KC_NUBS",
    0x65: "KC_APP", 0x67: "KC_PEQL",
    0xA5: "KC_PWR", 0xA6: "KC_SLEP", 0xA7: "KC_WAKE", 0xA8: "KC_MUTE",
    0xA9: "KC_VOLU", 0xAA: "KC_VOLD", 0xAB: "KC_MNXT", 0xAC: "KC_MPRV",
    0xAD: "KC_MSTP", 0xAE: "KC_MPLY", 0xAF: "KC_MSEL", 0xB0: "KC_EJCT",
    0xB1: "KC_MAIL", 0xB2: "KC_CALC", 0xB3: "KC_MYCM", 0xB4: "KC_WSCH",
    0xB5: "KC_WHOM", 0xB6: "KC_WBAK", 0xB7: "KC_WFWD", 0xB8: "KC_WSTP",
    0xB9: "KC_WREF", 0xBA: "KC_WFAV",
    0xE0: "KC_LCTL", 0xE1: "KC_LSFT", 0xE2: "KC_LALT", 0xE3: "KC_LGUI",
    0xE4: "KC_RCTL", 0xE5: "KC_RSFT", 0xE6: "KC_RALT", 0xE7: "KC_RGUI",
}
for i in range(26):
    BASIC[0x04 + i] = "KC_" + chr(ord("A") + i)
for i in range(9):
    BASIC[0x1E + i] = f"KC_{i + 1}"
    BASIC[0x59 + i] = f"KC_P{i + 1}"
BASIC[0x27] = "KC_0"
for i in range(12):
    BASIC[0x3A + i] = f"KC_F{i + 1}"
    BASIC[0x68 + i] = f"KC_F{i + 13}"

# Friendly aliases accepted on input
ALIASES = {
    "KC_ENTER": "KC_ENT", "KC_ESCAPE": "KC_ESC", "KC_BACKSPACE": "KC_BSPC",
    "KC_SPACE": "KC_SPC", "KC_DELETE": "KC_DEL", "KC_INSERT": "KC_INS",
    "KC_CAPS_LOCK": "KC_CAPS", "KC_RIGHT": "KC_RGHT", "KC_PAGE_UP": "KC_PGUP",
    "KC_PAGE_DOWN": "KC_PGDN", "KC_TRANSPARENT": "KC_TRNS", "_______": "KC_TRNS",
    "XXXXXXX": "KC_NO", "KC_MENU": "KC_APP", "KC_LCTRL": "KC_LCTL",
    "KC_RCTRL": "KC_RCTL", "KC_LSHIFT": "KC_LSFT", "KC_RSHIFT": "KC_RSFT",
    "KC_LWIN": "KC_LGUI", "KC_RWIN": "KC_RGUI", "KC_PLAY": "KC_MPLY",
    "KC_NEXT": "KC_MNXT", "KC_PREV": "KC_MPRV",
}

# Akko's custom keycodes from its VIA definition (USER/CUSTOM 0..6)
AKKO_CUSTOM = ["BT_DEV1", "BT_DEV2", "BT_DEV3", "BT_DEV4", "BT_DEV5",
               "DEV_2G4", "DEV_USB"]


class Keycodes:
    """Encoder/decoder for one VIA protocol version."""

    def __init__(self, protocol=12):
        if protocol >= 12:
            self.layer = {"TO": 0x5200, "MO": 0x5220, "DF": 0x5240,
                          "TG": 0x5260, "OSL": 0x5280, "TT": 0x52C0}
            self.layer_span = 0x20
            self.custom_base = 0x7E00
            self.macro_base = 0x7700
            self.special = {
                0x7C00: "QK_BOOT", 0x7820: "RGB_TOG", 0x7821: "RGB_MOD",
                0x7822: "RGB_RMOD", 0x7823: "RGB_HUI", 0x7824: "RGB_HUD",
                0x7825: "RGB_SAI", 0x7826: "RGB_SAD", 0x7827: "RGB_VAI",
                0x7828: "RGB_VAD", 0x7829: "RGB_SPI", 0x782A: "RGB_SPD",
            }
        else:
            self.layer = {"TO": 0x5010, "MO": 0x5100, "DF": 0x5200,
                          "TG": 0x5300, "OSL": 0x5400, "TT": 0x5800}
            self.layer_span = 0x10
            self.custom_base = 0x5F80
            self.macro_base = 0x5F12
            self.special = {0x5C00: "QK_BOOT"}
        self.by_name = {v: k for k, v in BASIC.items()}
        self.by_name.update({v: k for k, v in self.special.items()})
        for i, name in enumerate(AKKO_CUSTOM):
            self.by_name[name] = self.custom_base + i
        for i in range(16):
            self.by_name[f"M{i}"] = self.macro_base + i

    def name(self, code):
        if code in BASIC:
            return BASIC[code]
        if code in self.special:
            return self.special[code]
        if 0 <= code - self.macro_base < 16:
            return f"M{code - self.macro_base}"
        if 0 <= code - self.custom_base < len(AKKO_CUSTOM):
            return AKKO_CUSTOM[code - self.custom_base]
        if 0x0100 <= code <= 0x1FFF and (code & 0xFF) in BASIC:
            mods = code >> 8
            side = "R" if mods & 0x10 else "L"
            wrapped = BASIC[code & 0xFF]
            for bit, m in reversed(list(enumerate(MOD_NAMES))):
                if mods & (1 << bit):
                    wrapped = f"{side}{m}({wrapped})"
            return wrapped
        if 0x4000 <= code <= 0x4FFF and (code & 0xFF) in BASIC:
            return f"LT({(code >> 8) & 0xF},{BASIC[code & 0xFF]})"
        for fn, base in self.layer.items():
            if base <= code < base + self.layer_span:
                return f"{fn}({code - base})"
        return f"0x{code:04X}"

    def parse(self, text):
        t = text.strip().upper().replace(" ", "")
        if re.fullmatch(r"0X[0-9A-F]{1,4}", t):
            return int(t, 16)
        # exact name first, then allow "A", "ESC", "F5", "ENTER" without KC_
        for cand in (t, "KC_" + t):
            cand = ALIASES.get(cand, cand)
            if cand in self.by_name:
                return self.by_name[cand]
        m = re.fullmatch(r"(TO|MO|DF|TG|OSL|TT)\((\d+)\)", t)
        if m:
            return self.layer[m[1]] + int(m[2])
        m = re.fullmatch(r"LT\((\d+),(.+)\)", t)
        if m:
            return 0x4000 | (int(m[1]) << 8) | (self.parse(m[2]) & 0xFF)
        m = re.fullmatch(r"([LR])(CTL|SFT|ALT|GUI)\((.+)\)", t)
        if m:
            inner = self.parse(m[3])
            mods = (inner >> 8) | (1 << MOD_NAMES.index(m[2]))
            if m[1] == "R":
                mods |= 0x10
            return (mods << 8) | (inner & 0xFF)
        raise ValueError(f"Unknown keycode '{text}'")

    def all_names(self):
        names = sorted(self.by_name, key=lambda n: self.by_name[n])
        names += [f"MO({i})" for i in range(4)] + [f"TG({i})" for i in range(4)]
        return names


def short_label(name):
    """Compact text for drawing on a key cap."""
    label = name[3:] if name.startswith("KC_") else name
    return CAP_LABELS.get(label, label)


CAP_LABELS = {
    "TRNS": "▽", "NO": "✕", "MINS": "-", "EQL": "=", "LBRC": "[", "RBRC": "]",
    "BSLS": "\\", "SCLN": ";", "QUOT": "'", "GRV": "`", "COMM": ",", "DOT": ".",
    "SLSH": "/", "BSPC": "Backspace", "ENT": "Enter", "SPC": "Space",
    "LEFT": "←", "RGHT": "→", "UP": "↑", "DOWN": "↓", "VOLU": "Vol+",
    "VOLD": "Vol−", "MUTE": "Mute", "CAPS": "Caps", "LSFT": "Shift",
    "RSFT": "Shift", "LCTL": "Ctrl", "RCTL": "Ctrl", "LALT": "Alt",
    "RALT": "Alt", "LGUI": "Super", "RGUI": "Super", "ESC": "Esc", "TAB": "Tab",
    "DEL": "Del", "HOME": "Home", "END": "End", "PGUP": "PgUp", "PGDN": "PgDn",
    "MO(1)": "Fn", "NUBS": "<>", "NUHS": "#",
}
