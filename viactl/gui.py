"""GTK 3 app for lighting, keymap and macros."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import macros, via  # noqa: E402
from .keycodes import Keycodes, short_label  # noqa: E402
from .layout import layout_for  # noqa: E402

KEY_UNIT = 54
APPLY_DELAY_MS = 60     # coalesce slider drags into fewer USB writes
SAVE_DELAY_MS = 800     # write EEPROM once the user stops fiddling

FAILED = object()  # returned by App.call when a keyboard command fails

PRESETS = ["#ff0000", "#ff8000", "#ffff00", "#00ff00", "#00ffff",
           "#0060ff", "#8000ff", "#ff00ff", "#ffffff"]

CSS = b"""
.keycap { padding: 0; font-size: 10px; min-height: 0; min-width: 0; }
.keycap.changed { background-image: none; background-color: alpha(@theme_selected_bg_color, 0.35); }
.swatch { min-width: 26px; min-height: 26px; padding: 0; border-radius: 13px; }
.hint { opacity: 0.7; }
"""


class LightingPanel(Gtk.Grid):
    """Effect / brightness / speed / color controls for one lighting zone."""

    def __init__(self, app, zone):
        super().__init__(column_spacing=18, row_spacing=14, margin=24)
        self.app = app
        self.channel, self.effects, self.without_color = via.ZONES[zone]
        self._apply_src = self._save_src = None
        self._pending = {}
        self._loading = False
        self.hue = 0

        def label(text, row):
            self.attach(Gtk.Label(label=text, xalign=1), 0, row, 1, 1)

        label("Effect", 0)
        self.effect_combo = Gtk.ComboBoxText(hexpand=True)
        for i, name in enumerate(self.effects):
            self.effect_combo.append(str(i), f"{i:2}  {name}")
        self.effect_combo.connect("changed", self.on_effect)
        self.attach(self.effect_combo, 1, 0, 1, 1)

        label("Brightness", 1)
        self.bright_scale = self._scale(lambda v: self.queue(via.RGB_BRIGHTNESS, v))
        self.attach(self.bright_scale, 1, 1, 1, 1)

        label("Speed", 2)
        self.speed_scale = self._scale(lambda v: self.queue(via.RGB_SPEED, v))
        self.attach(self.speed_scale, 1, 2, 1, 1)

        label("Color", 3)
        color_box = Gtk.Box(spacing=8)
        self.color_button = Gtk.ColorButton(use_alpha=False)
        self.color_button.connect("color-set", self.on_color_button)
        color_box.pack_start(self.color_button, False, False, 0)
        for hexcolor in PRESETS:
            color_box.pack_start(self._swatch(hexcolor), False, False, 0)
        self.color_note = Gtk.Label(xalign=0)
        self.color_note.get_style_context().add_class("hint")
        color_box.pack_start(self.color_note, False, False, 8)
        self.attach(color_box, 1, 3, 1, 1)

        label("Saturation", 4)
        self.sat_scale = self._scale(lambda v: self.on_hue_sat())
        self.attach(self.sat_scale, 1, 4, 1, 1)

        bottom = Gtk.Box(spacing=12)
        self.autosave = Gtk.CheckButton(label="Save changes to the keyboard automatically", active=True)
        self.autosave.set_tooltip_text("When off, changes are lost when the keyboard is unplugged")
        bottom.pack_start(self.autosave, False, False, 0)
        save = Gtk.Button(label="Save now")
        save.connect("clicked", lambda *_: self.save())
        bottom.pack_end(save, False, False, 0)
        off = Gtk.Button(label="Lights off")
        off.connect("clicked", lambda *_: self.effect_combo.set_active_id("0"))
        bottom.pack_end(off, False, False, 0)
        self.attach(bottom, 0, 5, 2, 1)

        hint = Gtk.Label(
            label="Changes apply instantly. The keyboard must be connected by "
                  "USB cable in wired mode; VIA control is not available over "
                  "Bluetooth or 2.4G.", xalign=0, wrap=True)
        hint.get_style_context().add_class("hint")
        self.attach(hint, 0, 6, 2, 1)

    def _scale(self, on_change):
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_hexpand(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.connect("format-value", lambda _s, v: f"{v:.0f}%")
        scale.connect("value-changed",
                      lambda s: None if self._loading else on_change(round(s.get_value() * 2.55)))
        return scale

    def _swatch(self, hexcolor):
        b = Gtk.Button()
        b.get_style_context().add_class("swatch")
        b.set_tooltip_text(hexcolor)
        prov = Gtk.CssProvider()
        prov.load_from_data(f"button {{ background: {hexcolor}; }}".encode())
        b.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        b.connect("clicked", lambda *_: self.set_rgb_color(hexcolor))
        return b

    def load(self):
        state = self.app.call(lambda: self.app.kb.get_lighting(self.channel))
        if state is FAILED:
            return
        self._loading = True
        self.effect_combo.set_active_id(str(state["effect"]))
        self.bright_scale.set_value(state["brightness"] / 2.55)
        self.speed_scale.set_value(state["speed"] / 2.55)
        self.hue, sat = state["color"]
        self.sat_scale.set_value(sat / 2.55)
        self._show_color()
        self._update_color_note()
        self._loading = False

    def _show_color(self):
        r, g, b = via.hue_sat_to_rgb(self.hue, round(self.sat_scale.get_value() * 2.55))
        self.color_button.set_rgba(Gdk.RGBA(r / 255, g / 255, b / 255, 1))

    def _update_color_note(self):
        effect = int(self.effect_combo.get_active_id() or 0)
        self.color_note.set_text("This effect uses its own colors"
                                 if effect != 0 and effect in self.without_color else "")

    def on_effect(self, combo):
        self._update_color_note()
        if not self._loading and combo.get_active_id() is not None:
            self.queue(via.RGB_EFFECT, int(combo.get_active_id()))

    def on_color_button(self, button):
        c = button.get_rgba()
        self.set_rgb_color("#%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255)))

    def set_rgb_color(self, hexcolor):
        self.hue, sat = via.parse_color(hexcolor)
        self._loading = True
        self.sat_scale.set_value(sat / 2.55)
        self._loading = False
        self._show_color()
        self.queue(via.RGB_COLOR, (self.hue, sat))

    def on_hue_sat(self):
        self._show_color()
        self.queue(via.RGB_COLOR, (self.hue, round(self.sat_scale.get_value() * 2.55)))

    def queue(self, value_id, value):
        self._pending[value_id] = value
        if self._apply_src is None:
            self._apply_src = GLib.timeout_add(APPLY_DELAY_MS, self._apply)

    def _apply(self):
        self._apply_src = None
        pending, self._pending = self._pending, {}
        kb, ch = self.app.kb, self.channel
        setters = {via.RGB_BRIGHTNESS: lambda v: kb.set_brightness(v, ch),
                   via.RGB_EFFECT: lambda v: kb.set_effect(v, ch),
                   via.RGB_SPEED: lambda v: kb.set_speed(v, ch),
                   via.RGB_COLOR: lambda hs: kb.set_color(*hs, channel=ch)}
        for value_id, value in pending.items():
            if self.app.call(lambda: setters[value_id](value)) is FAILED:
                return False
        if self.autosave.get_active():
            if self._save_src:
                GLib.source_remove(self._save_src)
            self._save_src = GLib.timeout_add(SAVE_DELAY_MS, self._save_timeout)
        return False

    def _save_timeout(self):
        self._save_src = None
        self.save()
        return False

    def save(self):
        self.app.call(lambda: self.app.kb.save_lighting(self.channel))

    def flush(self):
        """Write a pending autosave now (used when the app closes)."""
        if self._save_src:
            GLib.source_remove(self._save_src)
            self._save_src = None
            self.save()


class App(Gtk.Window):
    def __init__(self, demo=False, device=None, layout=None):
        super().__init__(title="VIA Keyboard Control")
        self.set_default_size(1020, 660)
        self.demo, self.device, self.layout = demo, device, layout
        self.kb = None

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        header = Gtk.HeaderBar(show_close_button=True, title="VIA Keyboard Control")
        self.set_titlebar(header)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        header.set_custom_title(Gtk.StackSwitcher(stack=self.stack))
        reconnect = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        reconnect.set_tooltip_text("Reconnect and reload from the keyboard")
        reconnect.connect("clicked", lambda *_: self.connect_keyboard())
        header.pack_end(reconnect)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.infobar = Gtk.InfoBar(show_close_button=True, revealed=False)
        self.infobar.connect("response", lambda bar, _r: bar.set_revealed(False))
        self.info_label = Gtk.Label(wrap=True, xalign=0)
        self.infobar.get_content_area().add(self.info_label)
        box.pack_start(self.infobar, False, False, 0)
        box.pack_start(self.stack, True, True, 0)
        self.add(box)

        self.lighting = [LightingPanel(self, "keys"), LightingPanel(self, "side")]
        self.stack.add_titled(self.lighting[0], "lighting", "Backlight")
        self.stack.add_titled(self.lighting[1], "sidelights", "Sidelights")
        self.stack.add_titled(self.build_keymap(), "keymap", "Keymap")
        self.stack.add_titled(self.build_macros(), "macros", "Macros")
        self.stack.add_titled(self.build_device(), "device", "Device")

        self.connect("destroy", self.on_destroy)
        self.show_all()
        self.connect_keyboard()

    # -- connection / errors ---------------------------------------------
    def message(self, text, kind=Gtk.MessageType.ERROR):
        self.info_label.set_text(text)
        self.infobar.set_message_type(kind)
        self.infobar.set_revealed(True)

    def call(self, fn):
        """Run fn() against the keyboard; report failures instead of crashing.

        Returns fn's result, or FAILED.
        """
        if self.kb is None:
            self.message("Keyboard not connected. Plug it in by USB (wired "
                         "mode) and press the reload button.")
            return FAILED
        try:
            return fn()
        except (via.ViaError, OSError) as e:
            self.message(f"Keyboard error: {e}")
            return FAILED

    def connect_keyboard(self):
        if self.kb:
            self.kb.close()
            self.kb = None
        try:
            if self.demo:
                from .fake import fake_keyboard
                self.kb = fake_keyboard()
            else:
                self.kb = via.Keyboard.open(self.device)
        except (via.ViaError, OSError) as e:
            self.message(str(e))
            return
        self.kc = Keycodes(self.kb.protocol)
        self.infobar.set_revealed(False)
        if self.demo:
            self.message("Demo mode: using an emulated keyboard.", Gtk.MessageType.INFO)
        for panel in self.lighting:
            panel.load()
        self.load_keymap()
        self.load_macros()
        self.load_device()

    def on_destroy(self, *_):
        if self.kb:
            for panel in self.lighting:
                panel.flush()
        if self.kb:
            self.kb.close()
        Gtk.main_quit()

    # -- keymap -----------------------------------------------------------
    def build_keymap(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        top = Gtk.Box(spacing=10)
        top.pack_start(Gtk.Label(label="Layer"), False, False, 0)
        self.layer_combo = Gtk.ComboBoxText()
        self.layer_combo.connect("changed", lambda *_: self.draw_keymap())
        top.pack_start(self.layer_combo, False, False, 0)
        hint = Gtk.Label(label="Click a key to change what it does. Layer 0 is the "
                               "normal layer; layer 1 is usually reached by holding Fn.",
                         xalign=0, wrap=True)
        hint.get_style_context().add_class("hint")
        top.pack_start(hint, True, True, 8)
        box.pack_start(top, False, False, 0)

        self.key_area = Gtk.Fixed()
        self.key_buttons = {}
        scroller = Gtk.ScrolledWindow()
        scroller.set_min_content_height(int(6.75 * KEY_UNIT) + 8)
        scroller.add(self.key_area)
        box.pack_start(scroller, True, True, 0)

        reset = Gtk.Button(label="Reset keymap to factory default")
        reset.connect("clicked", self.on_reset_keymap)
        box.pack_start(reset, False, False, 0)
        self.keymap = None
        return box

    def build_keys(self):
        """(Re)create the key buttons for the connected keyboard's layout."""
        for b in self.key_buttons.values():
            b.destroy()
        self.key_buttons = {}
        for row, col, x, y, w, h in layout_for(self.kb.pid, self.layout):
            b = Gtk.Button()
            b.get_style_context().add_class("keycap")
            b.set_size_request(int(w * KEY_UNIT) - 4, int(h * KEY_UNIT) - 4)
            b.connect("clicked", self.on_key_clicked, row, col)
            self.key_area.put(b, int(x * KEY_UNIT), int(y * KEY_UNIT))
            self.key_buttons[(row, col)] = b
        self.key_area.show_all()

    def load_keymap(self):
        keymap = self.call(lambda: self.kb.get_keymap())
        if keymap is FAILED:
            return
        self.build_keys()
        self.keymap = keymap
        current = self.layer_combo.get_active()
        self.layer_combo.remove_all()
        for i in range(len(keymap)):
            self.layer_combo.append(str(i), f"{i}" + (" (base)" if i == 0 else ""))
        self.layer_combo.set_active(current if 0 <= current < len(keymap) else 0)

    def draw_keymap(self):
        layer = self.layer_combo.get_active()
        if self.keymap is None or layer < 0:
            return
        for (row, col), b in self.key_buttons.items():
            name = self.kc.name(self.keymap[layer][row][col])
            label = Gtk.Label(label=short_label(name), wrap=True, justify=Gtk.Justification.CENTER)
            label.set_max_width_chars(6)
            if b.get_child():
                b.remove(b.get_child())
            b.add(label)
            label.show()
            b.set_tooltip_text(f"{name}\nrow {row}, col {col}")

    def on_key_clicked(self, _button, row, col):
        layer = self.layer_combo.get_active()
        if self.keymap is None or layer < 0:
            return
        current = self.kc.name(self.keymap[layer][row][col])
        dialog = Gtk.Dialog(title=f"Remap key (row {row}, col {col}) on layer {layer}",
                            transient_for=self, modal=True)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Apply", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        area.add(Gtk.Label(label=f"Currently: {current}", xalign=0))
        entry = Gtk.Entry(text=current, activates_default=True)
        store = Gtk.ListStore(str)
        for n in self.kc.all_names():
            store.append([n])
        completion = Gtk.EntryCompletion(model=store, minimum_key_length=1)
        completion.set_text_column(0)
        entry.set_completion(completion)
        area.add(entry)
        help_text = Gtk.Label(
            label="Examples: KC_A, ESC, F5, KC_MUTE, MO(1), TG(2), LCTL(KC_C),\n"
                  "LT(1,KC_SPC), M0 (macro 0), KC_TRNS (fall through), KC_NO (disable),\n"
                  "BT_DEV1, DEV_USB, or a raw hex code like 0x7E00.", xalign=0)
        help_text.get_style_context().add_class("hint")
        area.add(help_text)
        dialog.show_all()
        while dialog.run() == Gtk.ResponseType.OK:
            try:
                code = self.kc.parse(entry.get_text())
            except ValueError as e:
                self.message(str(e))
                continue
            if self.call(lambda: self.kb.set_keycode(layer, row, col, code)) is not FAILED:
                self.keymap[layer][row][col] = code
                self.draw_keymap()
            break
        dialog.destroy()

    def confirm(self, text):
        d = Gtk.MessageDialog(transient_for=self, modal=True,
                              message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.OK_CANCEL, text=text)
        ok = d.run() == Gtk.ResponseType.OK
        d.destroy()
        return ok

    def on_reset_keymap(self, *_):
        if self.kb and self.confirm("Reset every layer of the keymap to the factory default?"):
            self.call(lambda: self.kb.reset_keymap())
            self.load_keymap()

    # -- macros -----------------------------------------------------------
    def build_macros(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=18)
        hint = Gtk.Label(
            label="Type text to send, plus {KC_ENTER} to tap a key, {+KC_LCTL} / "
                  "{-KC_LCTL} to hold / release, {200ms} to wait. Then assign "
                  "M0, M1… to a key on the Keymap tab.", xalign=0, wrap=True)
        hint.get_style_context().add_class("hint")
        box.pack_start(hint, False, False, 0)
        self.macro_grid = Gtk.Grid(column_spacing=10, row_spacing=6)
        scroller = Gtk.ScrolledWindow()
        scroller.add(self.macro_grid)
        box.pack_start(scroller, True, True, 0)
        self.macro_status = Gtk.Label(xalign=0)
        buttons = Gtk.Box(spacing=10)
        buttons.pack_start(self.macro_status, True, True, 0)
        write = Gtk.Button(label="Write macros to keyboard")
        write.get_style_context().add_class("suggested-action")
        write.connect("clicked", self.on_write_macros)
        buttons.pack_end(write, False, False, 0)
        box.pack_start(buttons, False, False, 0)
        self.macro_entries = []
        return box

    def load_macros(self):
        count = self.call(lambda: self.kb.get_macro_count())
        if count is FAILED or not count:
            return
        buf = self.call(lambda: self.kb.get_macro_buffer())
        if buf is FAILED:
            return
        texts = macros.decode(buf, count, self.kc)
        for child in self.macro_grid.get_children():
            self.macro_grid.remove(child)
        self.macro_entries = []
        for i, text in enumerate(texts):
            self.macro_grid.attach(Gtk.Label(label=f"M{i}", xalign=1), 0, i, 1, 1)
            e = Gtk.Entry(text=text, hexpand=True)
            self.macro_grid.attach(e, 1, i, 1, 1)
            self.macro_entries.append(e)
        self.macro_grid.show_all()
        self.macro_status.set_text(f"{len(buf)} bytes of macro storage")

    def on_write_macros(self, *_):
        try:
            data = macros.encode([e.get_text() for e in self.macro_entries], self.kc)
        except ValueError as e:
            self.message(str(e))
            return
        if self.call(lambda: self.kb.set_macro_buffer(data)) is not FAILED:
            self.macro_status.set_text(f"Saved ({len(data)} bytes used)")

    # -- device -----------------------------------------------------------
    def build_device(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=24)
        self.device_label = Gtk.Label(xalign=0, selectable=True)
        box.pack_start(self.device_label, False, False, 0)
        reset = Gtk.Button(label="Factory reset (keymap, macros and lighting)")
        reset.get_style_context().add_class("destructive-action")
        reset.connect("clicked", self.on_factory_reset)
        box.pack_end(reset, False, False, 0)
        return box

    def load_device(self):
        lines = []
        if self.demo:
            lines.append("Device: emulated keyboard (demo mode)")
        else:
            for d in via.find_devices():
                lines.append(f"Device: {d['name']}  {d['vid']:04x}:{d['pid']:04x}  {d['path']}")
        lines.append(f"VIA protocol: {self.kb.protocol}")
        for label, fn in (("Layers", self.kb.get_layer_count),
                          ("Macro slots", self.kb.get_macro_count)):
            try:
                lines.append(f"{label}: {fn()}")
            except via.ViaError as e:
                lines.append(f"{label}: unsupported ({e})")
        self.device_label.set_text("\n".join(lines))

    def on_factory_reset(self, *_):
        if self.kb and self.confirm("Erase all settings on the keyboard and restore factory defaults?"):
            if self.call(lambda: self.kb.factory_reset()) is not FAILED:
                self.message("Factory reset sent. Unplug and replug the keyboard, "
                             "then press reload.", Gtk.MessageType.INFO)


def main(demo=False, device=None, layout=None):
    App(demo=demo, device=device, layout=layout)
    Gtk.main()
