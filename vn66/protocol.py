"""Dukharo VN66 configuration protocol (64-byte HID feature reports, report id 0).

Worked out from the behaviour of the stock "Dukharo Driver" app for this keyboard
(firmware family "yzw", device id 224). Every request carries a checksum in byte 7:
255 - (sum(bytes 0..6) & 255). The lighting command carries it in byte 8 instead.
"""
import time

USB_IDS = [(0x0461, 0x4002), (0x3151, 0x4003)]      # older and newer VN66 hardware
DEVICE_ID_VN66 = 224
DEVICE_ID_VN66_V2 = 282                              # 3151:4003 "Dukharo VN66 Wired"
DEVICE_IDS = (DEVICE_ID_VN66, DEVICE_ID_VN66_V2)

CMD_GET_VERSION = 0x80
CMD_GET_INFO = 0x8F
CMD_RESET = 0x02
CMD_SET_RATE, CMD_GET_RATE = 0x04, 0x84
CMD_GET_PROFILE = 0x85
CMD_SET_OPTION, CMD_GET_OPTION = 0x06, 0x86
CMD_SET_LIGHT, CMD_GET_LIGHT = 0x07, 0x87
CMD_SET_KEYMAP, CMD_GET_KEYMAP = 0x09, 0x89
CMD_SET_MACRO, CMD_GET_MACRO = 0x0B, 0x8B
CMD_SET_PERKEY, CMD_GET_PERKEY = 0x0C, 0x8C
CMD_SET_FN, CMD_GET_FN = 0x10, 0x90

MATRIX_ENTRIES = 128
MATRIX_BYTES = MATRIX_ENTRIES * 4
KEYMAP_WRITE_BYTES = 9 * 56          # the firmware accepts 9 pages of 56 bytes
PERKEY_BYTES = 384
MACRO_SLOTS = 20
MACRO_BYTES = 256
MACRO_MAX_USED = 246
MAX_LEVEL = 4                        # brightness and speed both run 0..4

RATE_CODES = {1000: 1, 500: 2, 250: 4, 125: 8}
RATE_FROM_CODE = {v: k for k, v in RATE_CODES.items()}

OPT_WIN_LOCK = 1 << 0
OPT_MAC_LAYOUT = 1 << 1                # swaps Alt and Win (found on real hardware)
OPT_WASD_SWAP = 1 << 2

COLOR_RAINBOW = 7
COLOR_CUSTOM = 8
PRESET_COLORS = {0: (255, 0, 0), 1: (0, 255, 0), 2: (0, 0, 255), 3: (255, 85, 0),
                 4: (119, 0, 255), 5: (255, 255, 0), 6: (255, 255, 255)}

# id, key, label, has_speed, has_colour, direction options (label -> high nibble)
LIGHT_MODES = [
    (0, "off", "Off", False, False, None),
    (1, "static", "Static", False, True, None),
    (2, "breath", "Breathing", True, True, None),
    (3, "neon", "Neon", True, False, None),
    (4, "wave", "Wave", True, True, {"Right": 0, "Left": 1, "Down": 2, "Up": 3}),
    (5, "ripple", "Ripple", True, True, None),
    (6, "raindrop", "Raindrop", True, True, None),
    (7, "snake", "Snake", True, True, {"Zig-zag": 0, "Back and forth": 1}),
    (8, "reactive", "Reactive (light on press)", True, True, None),
    (9, "converge", "Converge", True, True, None),
    (10, "sine", "Sine wave", True, True, None),
    (11, "kaleidoscope", "Kaleidoscope", True, True, {"Outward": 0, "Inward": 1}),
    (12, "linewave", "Line wave", True, False, None),
    (14, "laser", "Laser", True, True, None),
    (15, "circle", "Circle wave", True, True, {"Anti-clockwise": 0, "Clockwise": 1}),
    (16, "dazzle", "Dazzle", True, True, None),
    (13, "perkey", "Custom per-key colours", False, False, None),
]
MODE_BY_ID = {m[0]: m for m in LIGHT_MODES}

DEFAULT_MATRIX = bytes([
    0,0,0,0, 0,0,41,0, 0,0,43,0, 0,0,57,0, 0,0,225,0, 0,0,224,0, 0,0,0,0, 0,0,30,0, 0,0,20,0, 0,0,4,0,
    0,0,100,0, 0,0,0,0, 0,0,0,0, 0,0,31,0, 0,0,26,0, 0,0,22,0, 0,0,29,0, 0,0,227,0, 0,0,0,0, 0,0,32,0,
    0,0,8,0, 0,0,7,0, 0,0,27,0, 0,0,226,0, 0,0,0,0, 0,0,33,0, 0,0,21,0, 0,0,9,0, 0,0,6,0, 0,0,0,0,
    0,0,0,0, 0,0,34,0, 0,0,23,0, 0,0,10,0, 0,0,25,0, 0,0,0,0, 0,0,0,0, 0,0,35,0, 0,0,28,0, 0,0,11,0,
    0,0,5,0, 0,0,44,0, 0,0,0,0, 0,0,36,0, 0,0,24,0, 0,0,13,0, 0,0,17,0, 0,0,0,0, 0,0,0,0, 0,0,37,0,
    0,0,12,0, 0,0,14,0, 0,0,16,0, 0,0,230,0, 0,0,0,0, 0,0,38,0, 0,0,18,0, 0,0,15,0, 0,0,54,0, 10,1,0,0,
    0,0,0,0, 0,0,39,0, 0,0,19,0, 0,0,51,0, 0,0,55,0, 0,0,0,0, 0,0,0,0, 0,0,45,0, 0,0,47,0, 0,0,52,0,
    0,0,56,0, 0,0,228,0, 0,0,0,0, 0,0,46,0, 0,0,48,0, 0,0,0,0, 0,0,229,0, 0,0,80,0, 0,0,0,0, 0,0,42,0,
    0,0,49,0, 0,0,40,0, 0,0,82,0, 0,0,81,0, 0,0,0,0, 3,0,226,0, 0,0,75,0, 0,0,78,0, 0,0,0,0, 0,0,79,0,
    3,0,234,0, 3,0,233,0,
]).ljust(MATRIX_BYTES, b"\0")


KNOB_PRESS = 85

# Factory Fn layer, as read from a VN66 (device id 282, firmware 774). Index = matrix position.
_FN = [(1, [0, 0, 53, 0]), (7, [0, 0, 58, 0]), (8, [14, 0, 1, 0]), (9, [3, 0, 205, 0]), (13, [0, 0, 59, 0]),
       (14, [14, 0, 2, 0]), (15, [3, 0, 182, 0]), (17, [10, 3, 0, 0]), (19, [0, 0, 60, 0]), (20, [14, 0, 3, 0]),
       (21, [3, 0, 181, 0]), (25, [0, 0, 61, 0]), (26, [14, 0, 0, 0]), (31, [0, 0, 62, 0]), (32, [14, 0, 4, 0]),
       (37, [0, 0, 63, 0]), (38, [10, 8, 0, 0]), (43, [0, 0, 64, 0]), (44, [0, 0, 70, 0]), (45, [0, 0, 73, 0]),
       (49, [0, 0, 65, 0]), (50, [0, 0, 71, 0]), (51, [0, 0, 74, 0]), (52, [10, 5, 3, 0]), (55, [0, 0, 66, 0]),
       (56, [0, 0, 72, 0]), (57, [0, 0, 77, 0]), (61, [0, 0, 67, 0]), (62, [13, 5, 1, 0]), (67, [0, 0, 68, 0]),
       (73, [0, 0, 69, 0]), (77, [13, 3, 1, 0]), (79, [10, 12, 0, 0]), (80, [13, 1, 0, 0]), (82, [13, 2, 1, 0]),
       (83, [13, 2, 2, 0]), (87, [0, 0, 76, 0]), (89, [13, 3, 2, 0])]
_fn = bytearray(MATRIX_BYTES)
for _i, _e in _FN:
    _fn[_i * 4:_i * 4 + 4] = bytes(_e)
DEFAULT_FN = bytes(_fn)
FN_LAYER = 0


def default_matrix(dev_id):
    """Factory key map. The newer hardware has the two knob-turn entries the other way round."""
    m = bytearray(DEFAULT_MATRIX)
    if dev_id == DEVICE_ID_VN66_V2:
        m[90 * 4:91 * 4], m[91 * 4:92 * 4] = DEFAULT_MATRIX[91 * 4:92 * 4], DEFAULT_MATRIX[90 * 4:91 * 4]
    return bytes(m)


def knob_indices(dev_id):
    """Matrix indices for knob turn-left / press / turn-right."""
    return {"left": 91, "press": KNOB_PRESS, "right": 90} if dev_id == DEVICE_ID_VN66_V2 else            {"left": 90, "press": KNOB_PRESS, "right": 91}


class ProtocolError(Exception):
    pass


def checksum7(buf):
    buf[7] = 255 - (sum(buf[:7]) & 255)
    return buf


def request(cmd, *args):
    buf = bytearray(64)
    buf[0] = cmd
    for i, a in enumerate(args):
        buf[1 + i] = a & 255
    return checksum7(buf)


# ---------------------------------------------------------------- lighting

def encode_light(light):
    mode = MODE_BY_ID.get(int(light.get("mode", 0)))
    if mode is None:
        raise ProtocolError("unknown lighting mode")
    mid, _, _, has_speed, has_colour, options = mode
    speed = min(MAX_LEVEL, max(0, int(light.get("speed", 2)))) if has_speed else 0
    bright = min(MAX_LEVEL, max(0, int(light.get("brightness", MAX_LEVEL))))
    opt = 7
    r = g = b = 0
    if has_colour:
        colour_code = COLOR_RAINBOW if light.get("rainbow") else COLOR_CUSTOM
        direction = int(light.get("option", 0)) if options else 0
        if options and direction not in options.values():
            direction = 0
        opt = (direction << 4) | colour_code
        r, g, b = hex_to_rgb(light.get("color", "#ffffff"))
        if (r, g, b) == (255, 255, 255):
            r, g, b = 250, 255, 250          # the firmware's own stand-in for pure white
    if mid == 13:
        opt, (r, g, b) = 0, (0, 200, 200)
    if mid == 0:
        bright = 0
    buf = bytearray(64)
    buf[0:8] = bytes([CMD_SET_LIGHT, mid, MAX_LEVEL - speed, bright, opt, r, g, b])
    buf[8] = 255 - (sum(buf[:8]) & 255)
    return buf


def decode_light(resp):
    mid, speed, bright, opt = resp[1], MAX_LEVEL - resp[2], resp[3], resp[4]
    rgb = (resp[5], resp[6], resp[7])
    if rgb == (250, 255, 250):
        rgb = (255, 255, 255)
    low, high = opt & 15, opt >> 4
    known = mid in MODE_BY_ID
    mode = MODE_BY_ID.get(mid, (mid, "", "", True, True, None))
    if low in PRESET_COLORS and mode[4]:
        rgb = PRESET_COLORS[low]
    return {
        "mode": mid, "known": known,
        "speed": min(MAX_LEVEL, max(0, speed)),
        "brightness": min(MAX_LEVEL, max(0, bright)),
        "rainbow": bool(mode[4] and low == COLOR_RAINBOW),
        "color": rgb_to_hex(rgb),
        "option": high if mode[5] else 0,
    }


def hex_to_rgb(text):
    text = str(text).lstrip("#")
    if len(text) != 6:
        raise ProtocolError("bad colour")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


# ------------------------------------------------------------------ macros
# Layout: u16 repeat count, then records. A record is [code, attr]; attr bit 7 is
# "key down", attr bits 0-6 an inline delay in ms. If the inline delay is zero the
# record is followed by a u16 delay. Code 0 is "no key" (a bare delay).

def encode_macro(repeat, events):
    """events: [{"t": "down"|"up", "k": hid_code} | {"t": "delay", "ms": n}]"""
    out = bytearray(2)
    out[0:2] = int(min(65535, max(1, repeat))).to_bytes(2, "little")
    i = 0
    events = [e for e in events if not (e["t"] == "delay" and int(e["ms"]) <= 0)]
    while i < len(events):
        e = events[i]
        if e["t"] == "delay":
            code, attr = 0, 0
            delay = int(e["ms"])
            i += 1
        else:
            code = int(e["k"])
            if not 1 <= code <= 248:
                raise ProtocolError("macro key code out of range")
            attr = 0x80 if e["t"] == "down" else 0
            delay = 0
            i += 1
            if i < len(events) and events[i]["t"] == "delay":
                delay = int(events[i]["ms"])
                i += 1
        delay = min(65535, max(0, delay))
        if 0 < delay <= 127:
            out += bytes([code, attr | delay])
        else:
            out += bytes([code, attr]) + delay.to_bytes(2, "little")
    if len(out) > MACRO_MAX_USED:
        raise ProtocolError("macro is too long for one slot (%d of %d bytes)" % (len(out), MACRO_MAX_USED))
    return bytes(out).ljust(MACRO_BYTES, b"\0")


def decode_macro(raw):
    """Returns {"repeat", "events"} or None for an empty / unreadable slot."""
    raw = bytes(raw[:MACRO_BYTES]).ljust(MACRO_BYTES, b"\0")
    repeat = int.from_bytes(raw[0:2], "little")
    events = []
    pos = 2
    while pos + 2 <= MACRO_BYTES - 2:
        code, attr = raw[pos], raw[pos + 1]
        inline = attr & 0x7F
        if inline:
            delay, size = inline, 2
        else:
            delay, size = int.from_bytes(raw[pos + 2:pos + 4], "little"), 4
        if code == 0 and attr == 0 and delay == 0:
            break
        if code == 0xFF and attr == 0xFF:          # erased flash
            return None
        if code:
            events.append({"t": "down" if attr & 0x80 else "up", "k": code})
        if delay:
            events.append({"t": "delay", "ms": delay})
        pos += size
    if not events or repeat in (0, 0xFFFF):
        return None
    return {"repeat": repeat, "events": events}


# ---------------------------------------------------------------- keyboard

class Keyboard:
    """Talks to anything with set_feature(payload) / get_feature() -> 64 bytes."""

    def __init__(self, dev, fast=False):
        self.dev = dev
        self.profile = 0
        self.fast = fast            # the simulator needs no settling time

    def _sleep(self, seconds):
        if not self.fast:
            time.sleep(seconds)

    # Measured on real hardware: after any write that is saved to flash the keyboard must be
    # left completely alone (about 1 s for settings, 2-3 s for the key map). Talking to it
    # during that window hangs its USB control channel for up to 90 s, so writes book a quiet
    # period and every later report waits it out.
    QUIET_SETTING = 2.0
    QUIET_TABLE = 4.0

    def _quiet(self, seconds):
        if not self.fast:
            self.quiet_until = time.time() + seconds

    def _send(self, buf, settle=0.012):
        wait = getattr(self, "quiet_until", 0) - time.time()
        if wait > 0:
            time.sleep(wait)
        self._sleep(settle)
        for attempt in range(6):
            try:
                self.dev.set_feature(bytes(buf))
                return
            except OSError:
                if attempt == 5 or self.fast:
                    raise
                time.sleep(15)                   # hung: give it a long rest before trying again

    def _query(self, buf, echo=True):
        """Send a request and read the reply. Simple replies echo the command byte."""
        for attempt in range(4):
            self._send(buf)
            self._sleep(0.008)
            resp = self.dev.get_feature()
            if len(resp) < 64:
                raise ProtocolError("short reply from keyboard")
            if not echo or resp[0] == buf[0]:
                return resp
            time.sleep(3)
        raise ProtocolError("the keyboard did not answer (command 0x%02x)" % buf[0])

    def _pages(self, cmd, arg, count):
        return b"".join(self._query(request(cmd, arg, page), echo=False) for page in range(count))

    # identity
    def device_id(self):
        for _ in range(5):
            resp = self._query(request(CMD_GET_INFO))
            value = int.from_bytes(resp[1:5], "little")
            if value:
                return value
            self._sleep(0.3)
        return 0

    def firmware_version(self):
        return int.from_bytes(self._query(request(CMD_GET_VERSION))[1:3], "little")

    def read_profile(self):
        value = self._query(request(CMD_GET_PROFILE))[1]
        self.profile = value if value < 8 else 0
        return self.profile

    # polling rate and options
    def get_rate(self):
        return RATE_FROM_CODE.get(self._query(request(CMD_GET_RATE, self.profile))[2])

    def set_rate(self, hz):
        if hz not in RATE_CODES:
            raise ProtocolError("unsupported polling rate")
        self._send(request(CMD_SET_RATE, self.profile, RATE_CODES[hz]))
        self._quiet(self.QUIET_SETTING)

    def get_option_bits(self):
        return self._query(request(CMD_GET_OPTION, self.profile))[2]

    def set_option_bits(self, bits):
        self._send(request(CMD_SET_OPTION, self.profile, bits & 0x1F))
        self._quiet(self.QUIET_SETTING)

    # lighting
    def get_light(self):
        return decode_light(self._query(request(CMD_GET_LIGHT)))

    def set_light(self, light):
        self._send(encode_light(light))
        self._quiet(self.QUIET_SETTING)

    def get_perkey(self):
        data = self._pages(CMD_GET_PERKEY, 0, 6)
        return data[:PERKEY_BYTES]

    def set_perkey(self, data):
        data = bytes(data).ljust(7 * 56, b"\xff")
        for page in range(7):
            head = request(CMD_SET_PERKEY, 0, PERKEY_BYTES & 255, PERKEY_BYTES >> 8, page)
            self._send(bytes(head[:8]) + data[page * 56:page * 56 + 56], settle=0.02)
        self._quiet(self.QUIET_TABLE)

    # key map
    def get_keymap(self):
        data = self._pages(CMD_GET_KEYMAP, self.profile, 8)
        return data[:MATRIX_BYTES]

    def set_keymap(self, matrix):
        matrix = bytes(matrix)
        if len(matrix) != MATRIX_BYTES:
            raise ProtocolError("key map must be %d bytes" % MATRIX_BYTES)
        for page in range(9):
            head = request(CMD_SET_KEYMAP, self.profile, 248, 1, page)
            self._send(bytes(head[:8]) + matrix[page * 56:page * 56 + 56])
        self._quiet(self.QUIET_TABLE)
        back = self.get_keymap()
        if back[:KEYMAP_WRITE_BYTES] != matrix[:KEYMAP_WRITE_BYTES]:
            raise ProtocolError("the keyboard did not store the key map (read-back differs)")

    # Fn layer (what each key does while Fn is held)
    def get_fn(self):
        return self._pages(CMD_GET_FN, FN_LAYER, 8)[:MATRIX_BYTES]

    def set_fn(self, matrix):
        matrix = bytes(matrix)
        if len(matrix) != MATRIX_BYTES:
            raise ProtocolError("Fn layer must be %d bytes" % MATRIX_BYTES)
        for page in range(9):
            head = request(CMD_SET_FN, FN_LAYER, 248, 1, page)
            self._send(bytes(head[:8]) + matrix[page * 56:page * 56 + 56])
        self._quiet(self.QUIET_TABLE)
        back = self.get_fn()
        if back[:KEYMAP_WRITE_BYTES] != matrix[:KEYMAP_WRITE_BYTES]:
            raise ProtocolError("the keyboard did not store the Fn layer (read-back differs)")

    # macros
    def get_macro(self, slot):
        data = self._pages(CMD_GET_MACRO, slot, 4)
        return decode_macro(data)

    def set_macro(self, slot, repeat, events):
        if not 0 <= slot < MACRO_SLOTS:
            raise ProtocolError("macro slot out of range")
        data = (encode_macro(repeat, events) if events else bytes(MACRO_BYTES)).ljust(5 * 56, b"\0")
        for page in range(5):
            head = request(CMD_SET_MACRO, slot, 0, 1, page)
            self._send(bytes(head[:8]) + data[page * 56:page * 56 + 56])
        self._quiet(self.QUIET_TABLE)

    def factory_reset(self):
        self._send(request(CMD_RESET))
        self._quiet(8.0)


# ------------------------------------------------------------- simulator

class SimDevice:
    """An in-memory stand-in for the keyboard, used by demo mode and the tests.

    It rejects frames with a bad checksum, so it exercises the framing above, but
    it only models the firmware as this app understands it.
    """

    def __init__(self):
        self.factory()
        self.reply = bytes(64)

    def factory(self):
        self.matrix = bytearray(DEFAULT_MATRIX)
        self.fn = bytearray(DEFAULT_FN)
        self.light = bytes([CMD_GET_LIGHT, 4, 2, 4, COLOR_RAINBOW, 0, 0, 0])
        self.perkey = bytearray(b"\0" * PERKEY_BYTES)
        self.macros = {}
        self.rate = 1
        self.options = 0

    def close(self):
        pass

    def set_feature(self, payload):
        p = bytes(payload).ljust(64, b"\0")
        cmd = p[0]
        if cmd == CMD_SET_LIGHT:
            if p[8] != 255 - (sum(p[:8]) & 255):
                raise OSError("sim: bad lighting checksum")
            self.light = bytes([CMD_GET_LIGHT]) + p[1:8]
            return
        if p[7] != 255 - (sum(p[:7]) & 255):
            raise OSError("sim: bad checksum")
        out = bytearray(64)
        out[0] = cmd
        if cmd == CMD_GET_INFO:
            out[1:5] = DEVICE_ID_VN66.to_bytes(4, "little")
        elif cmd == CMD_GET_VERSION:
            out[1:3] = (105).to_bytes(2, "little")
        elif cmd == CMD_GET_PROFILE:
            out[1] = 0
        elif cmd == CMD_GET_RATE:
            out[2] = self.rate
        elif cmd == CMD_SET_RATE:
            self.rate = p[2]
        elif cmd == CMD_GET_OPTION:
            out[2] = self.options
        elif cmd == CMD_SET_OPTION:
            self.options = p[2]
        elif cmd == CMD_GET_LIGHT:
            out[0:8] = self.light
        elif cmd == CMD_GET_KEYMAP:
            out = bytearray(self.matrix[p[2] * 64:p[2] * 64 + 64].ljust(64, b"\0"))
        elif cmd == CMD_SET_KEYMAP:
            start = p[4] * 56
            chunk = p[8:64][:max(0, MATRIX_BYTES - start)]
            self.matrix[start:start + len(chunk)] = chunk
        elif cmd == CMD_GET_FN:
            out = bytearray(self.fn[p[2] * 64:p[2] * 64 + 64].ljust(64, b"\0"))
        elif cmd == CMD_SET_FN:
            start = p[4] * 56
            chunk = p[8:64][:max(0, MATRIX_BYTES - start)]
            self.fn[start:start + len(chunk)] = chunk
        elif cmd == CMD_GET_PERKEY:
            out = bytearray(self.perkey[p[2] * 64:p[2] * 64 + 64].ljust(64, b"\0"))
        elif cmd == CMD_SET_PERKEY:
            start = p[4] * 56
            chunk = p[8:64][:max(0, PERKEY_BYTES - start)]
            self.perkey[start:start + len(chunk)] = chunk
        elif cmd == CMD_GET_MACRO:
            data = self.macros.get(p[1], bytes(MACRO_BYTES))
            out = bytearray(data[p[2] * 64:p[2] * 64 + 64].ljust(64, b"\0"))
        elif cmd == CMD_SET_MACRO:
            data = bytearray(self.macros.get(p[1], bytes(MACRO_BYTES)))
            start = p[4] * 56
            chunk = p[8:64][:max(0, MACRO_BYTES - start)]
            data[start:start + len(chunk)] = chunk
            self.macros[p[1]] = bytes(data)
        elif cmd == CMD_RESET:
            self.factory()
        self.reply = bytes(out)

    def get_feature(self):
        return self.reply
