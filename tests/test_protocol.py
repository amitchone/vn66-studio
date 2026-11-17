import os, sys, json, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vn66 import protocol as P

class Proto(unittest.TestCase):
    def setUp(self):
        self.sim = P.SimDevice(); self.kb = P.Keyboard(self.sim, fast=True)
    def test_identity(self):
        self.assertEqual(self.kb.device_id(), 224); self.assertEqual(self.kb.firmware_version(), 105)
    def test_checksum_matches_stock_app(self):
        # stock app: byte7 = 255 - (sum(bytes0..6) & 255)
        self.assertEqual(P.request(0x8F)[7], 0x70); self.assertEqual(P.request(0x89, 0, 3)[7], 255 - 0x8C)
    def test_default_matrix(self):
        m = P.DEFAULT_MATRIX; self.assertEqual(len(m), 512)
        at = lambda i: tuple(m[i*4:i*4+4])
        self.assertEqual(at(1), (0,0,41,0)); self.assertEqual(at(59), (10,1,0,0)); self.assertEqual(at(41), (0,0,44,0))
        self.assertEqual(at(85), (3,0,226,0)); self.assertEqual(at(90), (3,0,234,0)); self.assertEqual(at(91), (3,0,233,0)); self.assertEqual(at(89), (0,0,79,0))
    def test_keymap_roundtrip(self):
        m = bytearray(P.DEFAULT_MATRIX); m[3*4:3*4+4] = bytes([0,0,224,0]); m[89*4:89*4+4] = bytes([9,1,3,0])
        self.kb.set_keymap(m); self.assertEqual(self.kb.get_keymap(), bytes(m))
    def test_light(self):
        buf = P.encode_light({"mode": 4, "speed": 3, "brightness": 2, "rainbow": False, "color": "#ffffff", "option": 2})
        self.assertEqual(bytes(buf[:8]), bytes([7, 4, 1, 2, 0x28, 250, 255, 250])); self.assertEqual(buf[8], 255 - (sum(buf[:8]) & 255))
        for light in ({"mode": 4, "speed": 3, "brightness": 2, "rainbow": False, "color": "#ffffff", "option": 2},
                      {"mode": 1, "speed": 0, "brightness": 4, "rainbow": True, "color": "#102030", "option": 0},
                      {"mode": 15, "speed": 1, "brightness": 1, "rainbow": False, "color": "#102030", "option": 1}):
            self.kb.set_light(light); got = self.kb.get_light()
            for k in ("mode", "brightness", "rainbow", "option"): self.assertEqual(got[k], light[k], k)
            if not light["rainbow"]: self.assertEqual(got["color"], light["color"])
        self.kb.set_light({"mode": 13, "brightness": 3}); self.assertEqual(self.kb.get_light()["mode"], 13)
    def test_macro_bytes(self):
        ev = [{"t":"down","k":4},{"t":"delay","ms":50},{"t":"up","k":4},{"t":"delay","ms":300},{"t":"down","k":5},{"t":"up","k":5}]
        raw = P.encode_macro(2, ev)
        self.assertEqual(raw[:14], bytes([2,0, 4,0x80|50, 4,0,0x2C,0x01, 5,0x80,0,0, 5,0])); self.assertEqual(P.decode_macro(raw), {"repeat": 2, "events": ev})
    def test_macro_roundtrip_and_limits(self):
        ev = [{"t":"delay","ms":1000},{"t":"down","k":225},{"t":"down","k":4},{"t":"delay","ms":127},{"t":"up","k":4},{"t":"up","k":225},{"t":"delay","ms":128}]
        self.kb.set_macro(7, 3, ev); self.assertEqual(self.kb.get_macro(7), {"repeat": 3, "events": ev}); self.assertIsNone(self.kb.get_macro(8))
        self.kb.set_macro(7, 1, []); self.assertIsNone(self.kb.get_macro(7))
        with self.assertRaises(P.ProtocolError): P.encode_macro(1, [{"t":"down","k":4}] * 200)
        self.assertIsNone(P.decode_macro(b"\xff" * 256))
    def test_fn_layer(self):
        f = bytearray(self.kb.get_fn()); self.assertEqual(bytes(f), P.DEFAULT_FN); self.assertEqual(tuple(f[73*4:73*4+4]), (0,0,69,0))
        f[86*4:86*4+4] = bytes([0,0,69,0]); self.kb.set_fn(f); self.assertEqual(self.kb.get_fn(), bytes(f)); self.assertEqual(self.kb.get_keymap(), P.DEFAULT_MATRIX)
    def test_perkey(self):
        d = bytes(range(256)) + bytes(128); self.kb.set_perkey(d); self.assertEqual(self.kb.get_perkey(), d)
    def test_rate_options_reset(self):
        self.kb.set_rate(250); self.assertEqual(self.kb.get_rate(), 250)
        self.kb.set_option_bits(P.OPT_WIN_LOCK); self.assertEqual(self.kb.get_option_bits(), 1)
        self.kb.fast = True; self.kb.factory_reset(); self.assertEqual(self.kb.get_keymap(), P.DEFAULT_MATRIX)

if __name__ == "__main__":
    unittest.main()
