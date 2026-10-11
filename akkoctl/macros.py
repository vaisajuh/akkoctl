"""Convert VIA macro buffers to and from an editable text form.

Text syntax:
    plain text        typed as-is (US layout)
    {KC_ENTER}        tap a key
    {+KC_LCTL}        press and hold a key
    {-KC_LCTL}        release a key
    {250ms}           wait 250 milliseconds
    {{                a literal '{'
"""

import re

PREFIX = 0x01
TAP, DOWN, UP, DELAY = 0x01, 0x02, 0x03, 0x04

TOKEN = re.compile(r"\{\{|\{([+-]?)([^{}]+)\}")


def decode(buffer, count, kc):
    """Split the raw buffer into `count` macro strings."""
    macros = []
    parts = buffer.split(b"\x00")
    for raw in parts[:count]:
        out, i = [], 0
        while i < len(raw):
            b = raw[i]
            if b == PREFIX and i + 1 < len(raw):
                action = raw[i + 1]
                if action in (TAP, DOWN, UP) and i + 2 < len(raw):
                    sign = {TAP: "", DOWN: "+", UP: "-"}[action]
                    out.append("{" + sign + kc.name(raw[i + 2]) + "}")
                    i += 3
                    continue
                if action == DELAY:
                    end = raw.index(b"|", i) if b"|" in raw[i:] else len(raw)
                    out.append("{" + raw[i + 2:end].decode() + "ms}")
                    i = end + 1
                    continue
                if action in (5, 6, 7) and i + 3 < len(raw):
                    # extended keycode (2 bytes); shown as hex
                    sign = {5: "", 6: "+", 7: "-"}[action]
                    code = raw[i + 2] | (raw[i + 3] << 8)
                    out.append("{" + sign + f"0x{code:04X}" + "}")
                    i += 4
                    continue
            ch = chr(b)
            out.append("{{" if ch == "{" else ch)
            i += 1
        macros.append("".join(out))
    macros += [""] * (count - len(macros))
    return macros


def encode(macros, kc):
    """Serialise macro strings into one VIA macro buffer."""
    buf = bytearray()
    for text in macros:
        pos = 0
        for m in TOKEN.finditer(text):
            buf += _plain(text[pos:m.start()])
            pos = m.end()
            if m[0] == "{{":
                buf += b"{"
                continue
            sign, body = m[1], m[2].strip()
            delay = re.fullmatch(r"(\d+)\s*ms", body, re.I)
            if delay and not sign:
                buf += bytes([PREFIX, DELAY]) + delay[1].encode() + b"|"
                continue
            code = kc.parse(body)
            if code > 0xFF:
                raise ValueError(f"Macros only support basic keys, not {body}")
            action = {"": TAP, "+": DOWN, "-": UP}[sign]
            buf += bytes([PREFIX, action, code])
        buf += _plain(text[pos:])
        buf.append(0)
    return bytes(buf)


def _plain(s):
    for ch in s:
        if not (0x20 <= ord(ch) < 0x7F or ch in "\n\t"):
            raise ValueError(f"Character {ch!r} can't be typed by a macro; "
                             "use plain ASCII or {KC_...} tokens")
    return s.encode("ascii")
