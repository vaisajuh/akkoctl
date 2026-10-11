import unittest

from akkoctl import macros, via
from akkoctl.cli import main
from akkoctl.fake import FakeTransport
from akkoctl.keycodes import Keycodes
from akkoctl.layout import ANSI, ISO, layout_for


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.t = FakeTransport()
        self.kb = via.Keyboard(self.t)

    def test_lighting_roundtrip(self):
        self.kb.set_brightness(77)
        self.kb.set_effect(5)
        self.kb.set_speed(300)  # clamped
        self.kb.set_color(*via.parse_color("#00ff00"))
        self.kb.save_lighting()
        self.assertEqual(self.kb.get_lighting(),
                         {"brightness": 77, "effect": 5, "speed": 255, "color": (85, 255)})
        self.assertEqual(self.t.saved, 1)

    def test_lighting_packets(self):
        sent = []
        orig = self.t.transfer
        self.t.transfer = lambda p, timeout=1.0: (sent.append(p), orig(p))[1]
        self.kb.set_color(10, 20)
        self.kb.save_lighting()
        self.assertEqual(sent[0][:5], bytes([0x07, 3, 4, 10, 20]))
        self.assertEqual(sent[1][:2], bytes([0x09, 3]))
        self.assertTrue(all(len(p) == 32 for p in sent))

    def test_keymap_bulk_matches_single(self):
        self.kb.set_keycode(1, 2, 3, 0x7E00)
        keymap = self.kb.get_keymap()
        self.assertEqual(len(keymap), 4)
        for layer in (0, 1):
            for r in range(6):
                for c in range(15):
                    self.assertEqual(keymap[layer][r][c], self.kb.get_keycode(layer, r, c))

    def test_sidelight_channel_is_independent(self):
        side = via.CHANNEL_SIDELIGHT
        self.kb.set_effect(9, side)
        self.kb.set_color(0, 255, channel=side)
        self.kb.save_lighting(side)
        self.assertEqual(self.kb.get_effect(side), 9)
        self.assertEqual(self.kb.get_color(side), (0, 255))
        self.assertEqual(self.kb.get_effect(), 1)  # key backlight untouched
        self.assertEqual(len(via.SIDE_EFFECTS), 42)

    def test_unhandled_command_raises(self):
        with self.assertRaises(via.ViaError):
            self.kb.command(0x42)

    def test_layout_covers_matrix(self):
        for keys, n in ((ANSI, 83), (ISO, 84)):
            self.assertEqual(len({(r, c) for r, c, *_ in keys}), n)
            self.assertTrue(all(r < 6 and c < 15 for r, c, *_ in keys))
        self.assertIs(layout_for(0xE4F6), ISO)
        self.assertIs(layout_for(0xE4D7), ANSI)
        self.assertIs(layout_for(0xE4F6, "ansi"), ANSI)


class KeycodeTest(unittest.TestCase):
    kc = Keycodes(12)

    def test_roundtrip(self):
        for text in ["KC_A", "KC_F12", "KC_MUTE", "MO(1)", "TG(3)", "LCTL(KC_C)",
                     "RSFT(KC_1)", "LT(2,KC_SPC)", "BT_DEV3", "DEV_USB", "M5",
                     "KC_TRNS", "RGB_TOG", "QK_BOOT", "LCTL(LSFT(KC_ESC))"]:
            self.assertEqual(self.kc.name(self.kc.parse(text)), text, text)

    def test_friendly_input(self):
        self.assertEqual(self.kc.parse("esc"), 0x29)
        self.assertEqual(self.kc.parse("ENTER"), 0x28)
        self.assertEqual(self.kc.parse("mute"), 0xA8)
        self.assertEqual(self.kc.parse("mo(1)"), 0x5221)
        self.assertEqual(self.kc.parse("0x7e00"), 0x7E00)
        with self.assertRaises(ValueError):
            self.kc.parse("KC_BOGUS")

    def test_old_protocol(self):
        old = Keycodes(10)
        self.assertEqual(old.parse("MO(1)"), 0x5101)
        self.assertEqual(old.name(0x5101), "MO(1)")


class MacroTest(unittest.TestCase):
    kc = Keycodes(12)

    def test_roundtrip(self):
        texts = ["hello{KC_ENT}", "", "{+KC_LCTL}{KC_C}{-KC_LCTL}{100ms}x", "a{{b"]
        kb = via.Keyboard(FakeTransport())
        kb.set_macro_buffer(macros.encode(texts, self.kc))
        self.assertEqual(macros.decode(kb.get_macro_buffer(), 16, self.kc),
                         texts + [""] * 12)

    def test_encoding(self):
        self.assertEqual(macros.encode(["a{KC_B}{5ms}"], self.kc),
                         b"a\x01\x01\x05\x01\x045|\x00")

    def test_too_big(self):
        kb = via.Keyboard(FakeTransport(macro_size=8))
        with self.assertRaises(via.ViaError):
            kb.set_macro_buffer(macros.encode(["far too long"], self.kc))


class ColorTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(via.parse_color("red"), (0, 255))
        self.assertEqual(via.parse_color("#0000ff"), (170, 255))
        self.assertEqual(via.parse_color("hsv:12,34"), (12, 34))
        with self.assertRaises(ValueError):
            via.parse_color("nope")


class CliTest(unittest.TestCase):
    def test_commands_run(self):
        for argv in (["--demo", "info"], ["--demo", "set", "-e", "breathing", "-b", "50%", "-c", "cyan"],
                     ["--demo", "keymap", "--layer", "0"], ["--demo", "--layout", "iso", "keymap"], ["--demo", "remap", "1", "0", "0", "KC_GRV"],
                     ["--demo", "macro", "0", "hi{KC_ENT}"], ["--demo", "macro"], ["effects"], ["effects", "--side"],
                     ["--demo", "set", "--side", "-e", "snake 2", "-s", "30%"], ["--demo", "status", "--keys"]):
            main(argv)


if __name__ == "__main__":
    unittest.main()
