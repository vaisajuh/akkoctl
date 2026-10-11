"""An in-memory VIA keyboard, used by --demo and the tests."""

from . import via

DEFAULT_LAYER0 = [
    [0x29, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x4C, 0xA8],
    [0x35, 0x1E, 0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x2D, 0x2E, 0x2A, 0x4A],
    [0x2B, 0x14, 0x1A, 0x08, 0x15, 0x17, 0x1C, 0x18, 0x0C, 0x12, 0x13, 0x2F, 0x30, 0x31, 0x4B],
    [0x39, 0x04, 0x16, 0x07, 0x09, 0x0A, 0x0B, 0x0D, 0x0E, 0x0F, 0x33, 0x34, 0x00, 0x28, 0x4E],
    [0xE1, 0x00, 0x1D, 0x1B, 0x06, 0x19, 0x05, 0x11, 0x10, 0x36, 0x37, 0x38, 0xE5, 0x52, 0x4D],
    [0xE0, 0xE3, 0xE2, 0x00, 0x00, 0x00, 0x2C, 0x00, 0x00, 0xE6, 0x5221, 0xE4, 0x50, 0x51, 0x4F],
]


class FakeTransport:
    def __init__(self, layers=4, macro_count=16, macro_size=1024):
        self.rows, self.cols = via.MATRIX_ROWS, via.MATRIX_COLS
        self.layers = layers
        self.keymap = [[row[:] for row in DEFAULT_LAYER0]] + [
            [[0x01] * self.cols for _ in range(self.rows)]
            for _ in range(layers - 1)]
        self.rgb = {
            ch: {via.RGB_BRIGHTNESS: [200], via.RGB_EFFECT: [1],
                 via.RGB_SPEED: [128], via.RGB_COLOR: [hue, 255]}
            for ch, hue in ((via.CHANNEL_RGB_MATRIX, 170), (via.CHANNEL_SIDELIGHT, 40))}
        self.saved = 0
        self.macro_count = macro_count
        self.macros = bytearray(macro_size)

    def _flat_keymap(self):
        out = bytearray()
        for layer in self.keymap:
            for row in layer:
                for code in row:
                    out += code.to_bytes(2, "big")
        return out

    def transfer(self, packet, timeout=1.0):
        p = bytearray(packet)
        cmd = p[0]
        if cmd == via.CMD_GET_PROTOCOL_VERSION:
            p[1:3] = (12).to_bytes(2, "big")
        elif cmd == via.CMD_GET_KEYBOARD_VALUE:
            p[2:6] = (123456 if p[1] == via.KBV_UPTIME else 0x00010203).to_bytes(4, "big")
        elif cmd == via.CMD_KEYMAP_GET_KEYCODE:
            p[4:6] = self.keymap[p[1]][p[2]][p[3]].to_bytes(2, "big")
        elif cmd == via.CMD_KEYMAP_SET_KEYCODE:
            self.keymap[p[1]][p[2]][p[3]] = (p[4] << 8) | p[5]
        elif cmd == via.CMD_KEYMAP_GET_LAYER_COUNT:
            p[1] = self.layers
        elif cmd == via.CMD_KEYMAP_GET_BUFFER:
            off, n = (p[1] << 8) | p[2], p[3]
            p[4:4 + n] = self._flat_keymap()[off:off + n]
        elif cmd == via.CMD_CUSTOM_GET_VALUE and p[1] in self.rgb:
            vals = self.rgb[p[1]][p[2]]
            p[3:3 + len(vals)] = bytes(vals)
        elif cmd == via.CMD_CUSTOM_SET_VALUE and p[1] in self.rgb:
            zone = self.rgb[p[1]]
            zone[p[2]] = list(p[3:3 + len(zone[p[2]])])
        elif cmd == via.CMD_CUSTOM_SAVE:
            self.saved += 1
        elif cmd == via.CMD_MACRO_GET_COUNT:
            p[1] = self.macro_count
        elif cmd == via.CMD_MACRO_GET_BUFFER_SIZE:
            p[1:3] = len(self.macros).to_bytes(2, "big")
        elif cmd == via.CMD_MACRO_GET_BUFFER:
            off, n = (p[1] << 8) | p[2], p[3]
            p[4:4 + n] = self.macros[off:off + n]
        elif cmd == via.CMD_MACRO_SET_BUFFER:
            off, n = (p[1] << 8) | p[2], p[3]
            self.macros[off:off + n] = p[4:4 + n]
        elif cmd in (via.CMD_MACRO_RESET, via.CMD_KEYMAP_RESET, via.CMD_EEPROM_RESET):
            pass
        else:
            p[0] = via.CMD_UNHANDLED
        return bytes(p)

    def close(self):
        pass


def fake_keyboard():
    return via.Keyboard(FakeTransport())
