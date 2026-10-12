"""VIA raw-HID protocol for VIA keyboards (tested on the Akko 5075B Plus-S).

The keyboard exposes a vendor HID interface (usage page 0xFF60, usage 0x61)
that takes 32-byte command packets. This module finds that interface through
sysfs and talks to it via /dev/hidraw*, so it has no third-party dependencies.
"""

import colorsys
import glob
import os
import select

AKKO_VID = 0x342D
REPORT_SIZE = 32
# usage page 0xFF60 / usage 0x61 as they appear in a HID report descriptor
VIA_USAGE_SIG = bytes([0x06, 0x60, 0xFF, 0x09, 0x61])

# VIA command ids
CMD_GET_PROTOCOL_VERSION = 0x01
CMD_GET_KEYBOARD_VALUE = 0x02
CMD_KEYMAP_GET_KEYCODE = 0x04
CMD_KEYMAP_SET_KEYCODE = 0x05
CMD_KEYMAP_RESET = 0x06
CMD_CUSTOM_SET_VALUE = 0x07
CMD_CUSTOM_GET_VALUE = 0x08
CMD_CUSTOM_SAVE = 0x09
CMD_EEPROM_RESET = 0x0A
CMD_MACRO_GET_COUNT = 0x0C
CMD_MACRO_GET_BUFFER_SIZE = 0x0D
CMD_MACRO_GET_BUFFER = 0x0E
CMD_MACRO_SET_BUFFER = 0x0F
CMD_MACRO_RESET = 0x10
CMD_KEYMAP_GET_LAYER_COUNT = 0x11
CMD_KEYMAP_GET_BUFFER = 0x12
CMD_KEYMAP_SET_BUFFER = 0x13
CMD_UNHANDLED = 0xFF

# CMD_GET_KEYBOARD_VALUE sub-ids
KBV_UPTIME = 0x01
KBV_FIRMWARE_VERSION = 0x04

# Per-key backlight is the QMK RGB-matrix channel (per Akko's VIA definition);
# the side light strip answers on the QMK rgblight channel.
CHANNEL_SIDELIGHT = 2
CHANNEL_RGB_MATRIX = 3
RGB_BRIGHTNESS = 1
RGB_EFFECT = 2
RGB_SPEED = 3
RGB_COLOR = 4

MAX_CHUNK = REPORT_SIZE - 4

EFFECTS = [
    "All Off", "Solid Color", "Alphas Mods", "Gradient Up Down",
    "Gradient Left Right", "Breathing", "Band Sat", "Band Val",
    "Band Pinwheel Sat", "Band Pinwheel Val", "Band Spiral Sat",
    "Band Spiral Val", "Cycle All", "Cycle Left Right", "Cycle Up Down",
    "Rainbow Moving Chevron", "Cycle Out In", "Cycle Out In Dual",
    "Cycle Pinwheel", "Cycle Spiral", "Dual Beacon", "Rainbow Beacon",
    "Rainbow Pinwheels", "Raindrops", "Jellybean Raindrops", "Hue Breathing",
    "Hue Pendulum", "Hue Wave", "Pixel Rain", "Pixel Flow", "Pixel Fractal",
    "Typing Heatmap", "Digital Rain", "Solid Reactive Simple",
    "Solid Reactive", "Solid Reactive Wide", "Solid Reactive Multiwide",
    "Solid Reactive Cross", "Solid Reactive Multicross",
    "Solid Reactive Nexus", "Solid Reactive Multinexus", "Splash",
    "Multisplash", "Solid Splash", "Solid Multisplash", "Close All",
]
# effects whose colors are generated, so the color setting has no effect
EFFECTS_WITHOUT_COLOR = {0, 24, 28, 29, 32}

# QMK's standard rgblight effect order; the firmware accepts 0-41
SIDE_EFFECTS = [
    "All Off", "Solid Color", "Breathing 1", "Breathing 2", "Breathing 3",
    "Breathing 4", "Rainbow Mood 1", "Rainbow Mood 2", "Rainbow Mood 3",
    "Rainbow Swirl 1", "Rainbow Swirl 2", "Rainbow Swirl 3", "Rainbow Swirl 4",
    "Rainbow Swirl 5", "Rainbow Swirl 6", "Snake 1", "Snake 2", "Snake 3",
    "Snake 4", "Snake 5", "Snake 6", "Knight 1", "Knight 2", "Knight 3",
    "Christmas", "Gradient 1", "Gradient 2", "Gradient 3", "Gradient 4",
    "Gradient 5", "Gradient 6", "Gradient 7", "Gradient 8", "Gradient 9",
    "Gradient 10", "RGB Test", "Alternating", "Twinkle 1", "Twinkle 2",
    "Twinkle 3", "Twinkle 4", "Twinkle 5",
]
SIDE_EFFECTS_WITHOUT_COLOR = {0} | set(range(6, 15)) | {24, 35}

ZONES = {
    "keys": (CHANNEL_RGB_MATRIX, EFFECTS, EFFECTS_WITHOUT_COLOR),
    "side": (CHANNEL_SIDELIGHT, SIDE_EFFECTS, SIDE_EFFECTS_WITHOUT_COLOR),
}

MATRIX_ROWS = 6
MATRIX_COLS = 15


class ViaError(Exception):
    pass


def find_devices():
    """Return [(hidraw path, product name)] for every VIA interface found."""
    found = []
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(node, "device/uevent")) as f:
                uevent = dict(l.strip().split("=", 1) for l in f if "=" in l)
            with open(os.path.join(node, "device/report_descriptor"), "rb") as f:
                desc = f.read()
        except OSError:
            continue
        if VIA_USAGE_SIG not in desc:
            continue
        # HID_ID looks like 0003:0000342D:0000E4F6
        _, vid, pid = uevent.get("HID_ID", "0:0:0").split(":")
        found.append({
            "path": "/dev/" + os.path.basename(node),
            "name": uevent.get("HID_NAME", "?"),
            "vid": int(vid, 16),
            "pid": int(pid, 16),
        })
    # prefer Akko boards when several VIA keyboards are plugged in
    found.sort(key=lambda d: d["vid"] != AKKO_VID)
    return found


class HidrawTransport:
    def __init__(self, path):
        self.path = path
        try:
            self.fd = os.open(path, os.O_RDWR)
        except PermissionError:
            raise ViaError(
                f"Permission denied opening {path}. Install the udev rule "
                "once with ./install.sh (asks for your sudo password), then "
                "replug the keyboard.")

    def transfer(self, packet, timeout=1.0):
        # drop anything stale so replies line up with requests
        while select.select([self.fd], [], [], 0)[0]:
            os.read(self.fd, 64)
        # hidraw wants the report id first; the VIA interface has none (0)
        os.write(self.fd, b"\x00" + packet)
        if not select.select([self.fd], [], [], timeout)[0]:
            raise ViaError("Keyboard did not answer (is it in wired/USB mode?)")
        return os.read(self.fd, 64)[:REPORT_SIZE]

    def close(self):
        os.close(self.fd)


class Keyboard:
    """High-level VIA commands."""

    def __init__(self, transport, rows=MATRIX_ROWS, cols=MATRIX_COLS, pid=None):
        self.t = transport
        self.pid = pid
        self.rows = rows
        self.cols = cols
        self.protocol = self.get_protocol_version()

    @classmethod
    def open(cls, path=None):
        devices = find_devices()
        if path is None:
            if not devices:
                raise ViaError(
                    "No VIA keyboard found. Make sure the keyboard is connected "
                    "by USB cable and switched to wired mode.")
            path = devices[0]["path"]
        pid = next((d["pid"] for d in devices if d["path"] == path), None)
        return cls(HidrawTransport(path), pid=pid)

    def close(self):
        self.t.close()

    def command(self, *data):
        packet = bytes(data).ljust(REPORT_SIZE, b"\x00")
        reply = self.t.transfer(packet)
        if reply[0] == CMD_UNHANDLED and data[0] != CMD_UNHANDLED:
            raise ViaError(f"Keyboard does not support command 0x{data[0]:02X}")
        return reply

    # -- info -------------------------------------------------------------
    def get_protocol_version(self):
        r = self.command(CMD_GET_PROTOCOL_VERSION)
        return (r[1] << 8) | r[2]

    def get_uptime_ms(self):
        r = self.command(CMD_GET_KEYBOARD_VALUE, KBV_UPTIME)
        return int.from_bytes(r[2:6], "big")

    def get_firmware_version(self):
        r = self.command(CMD_GET_KEYBOARD_VALUE, KBV_FIRMWARE_VERSION)
        return int.from_bytes(r[2:6], "big")

    # -- lighting ---------------------------------------------------------
    # `channel` picks the zone: CHANNEL_RGB_MATRIX (keys) or CHANNEL_SIDELIGHT
    def _get_rgb(self, channel, value_id, n=1):
        r = self.command(CMD_CUSTOM_GET_VALUE, channel, value_id)
        return list(r[3:3 + n])

    def _set_rgb(self, channel, value_id, *values):
        self.command(CMD_CUSTOM_SET_VALUE, channel, value_id, *values)

    def get_brightness(self, channel=CHANNEL_RGB_MATRIX):
        return self._get_rgb(channel, RGB_BRIGHTNESS)[0]

    def set_brightness(self, value, channel=CHANNEL_RGB_MATRIX):
        self._set_rgb(channel, RGB_BRIGHTNESS, clamp(value))

    def get_effect(self, channel=CHANNEL_RGB_MATRIX):
        return self._get_rgb(channel, RGB_EFFECT)[0]

    def set_effect(self, value, channel=CHANNEL_RGB_MATRIX):
        self._set_rgb(channel, RGB_EFFECT, clamp(value))

    def get_speed(self, channel=CHANNEL_RGB_MATRIX):
        return self._get_rgb(channel, RGB_SPEED)[0]

    def set_speed(self, value, channel=CHANNEL_RGB_MATRIX):
        self._set_rgb(channel, RGB_SPEED, clamp(value))

    def get_color(self, channel=CHANNEL_RGB_MATRIX):
        """Return (hue, saturation), both 0-255."""
        return tuple(self._get_rgb(channel, RGB_COLOR, 2))

    def set_color(self, hue, sat, channel=CHANNEL_RGB_MATRIX):
        self._set_rgb(channel, RGB_COLOR, clamp(hue), clamp(sat))

    def get_lighting(self, channel=CHANNEL_RGB_MATRIX):
        return {
            "brightness": self.get_brightness(channel),
            "effect": self.get_effect(channel),
            "speed": self.get_speed(channel),
            "color": self.get_color(channel),
        }

    def save_lighting(self, channel=CHANNEL_RGB_MATRIX):
        """Persist the zone's current lighting to the keyboard's EEPROM."""
        self.command(CMD_CUSTOM_SAVE, channel)

    # -- keymap -----------------------------------------------------------
    def get_layer_count(self):
        return self.command(CMD_KEYMAP_GET_LAYER_COUNT)[1]

    def get_keycode(self, layer, row, col):
        r = self.command(CMD_KEYMAP_GET_KEYCODE, layer, row, col)
        return (r[4] << 8) | r[5]

    def set_keycode(self, layer, row, col, keycode):
        self.command(CMD_KEYMAP_SET_KEYCODE, layer, row, col,
                     keycode >> 8, keycode & 0xFF)

    def get_keymap(self):
        """Return keymap[layer][row][col] read in bulk."""
        layers = self.get_layer_count()
        size = layers * self.rows * self.cols * 2
        raw = self._read_buffer(CMD_KEYMAP_GET_BUFFER, size)
        codes = [(raw[i] << 8) | raw[i + 1] for i in range(0, size, 2)]
        per_layer = self.rows * self.cols
        return [[codes[l * per_layer + r * self.cols:
                       l * per_layer + (r + 1) * self.cols]
                 for r in range(self.rows)] for l in range(layers)]

    def reset_keymap(self):
        self.command(CMD_KEYMAP_RESET)

    # -- macros -----------------------------------------------------------
    def get_macro_count(self):
        return self.command(CMD_MACRO_GET_COUNT)[1]

    def get_macro_buffer_size(self):
        r = self.command(CMD_MACRO_GET_BUFFER_SIZE)
        return (r[1] << 8) | r[2]

    def get_macro_buffer(self):
        return self._read_buffer(CMD_MACRO_GET_BUFFER,
                                 self.get_macro_buffer_size())

    def set_macro_buffer(self, data):
        size = self.get_macro_buffer_size()
        if len(data) > size:
            raise ViaError(f"Macros need {len(data)} bytes but the keyboard "
                           f"only has room for {size}")
        data = bytes(data).ljust(size, b"\x00")
        for off in range(0, size, MAX_CHUNK):
            chunk = data[off:off + MAX_CHUNK]
            self.command(CMD_MACRO_SET_BUFFER, off >> 8, off & 0xFF,
                         len(chunk), *chunk)

    def reset_macros(self):
        self.command(CMD_MACRO_RESET)

    # -- misc -------------------------------------------------------------
    def factory_reset(self):
        """Wipe EEPROM: keymap, macros and lighting go back to defaults."""
        self.command(CMD_EEPROM_RESET)

    def _read_buffer(self, cmd, size):
        out = bytearray()
        for off in range(0, size, MAX_CHUNK):
            n = min(MAX_CHUNK, size - off)
            r = self.command(cmd, off >> 8, off & 0xFF, n)
            out += r[4:4 + n]
        return bytes(out)


def clamp(v):
    return max(0, min(255, int(v)))


def rgb_to_hue_sat(r, g, b):
    h, s, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return round(h * 255) % 256, round(s * 255)


def hue_sat_to_rgb(hue, sat, val=255):
    r, g, b = colorsys.hsv_to_rgb(hue / 255, sat / 255, val / 255)
    return round(r * 255), round(g * 255), round(b * 255)


NAMED_COLORS = {
    "red": (255, 0, 0), "orange": (255, 128, 0), "yellow": (255, 255, 0),
    "green": (0, 255, 0), "cyan": (0, 255, 255), "blue": (0, 0, 255),
    "purple": (128, 0, 255), "magenta": (255, 0, 255), "pink": (255, 105, 180),
    "white": (255, 255, 255),
}


def parse_color(text):
    """Accept '#ff8800', 'ff8800', a color name, or 'hsv:H,S' (0-255)."""
    t = text.strip().lower()
    if t.startswith("hsv:"):
        h, s = (int(x) for x in t[4:].split(","))
        return clamp(h), clamp(s)
    if t in NAMED_COLORS:
        return rgb_to_hue_sat(*NAMED_COLORS[t])
    t = t.lstrip("#")
    if len(t) == 6:
        try:
            return rgb_to_hue_sat(*(int(t[i:i + 2], 16) for i in (0, 2, 4)))
        except ValueError:
            pass
    raise ValueError(f"Unrecognised color '{text}'. Use #RRGGBB, a name "
                     f"({', '.join(NAMED_COLORS)}) or hsv:H,S")
