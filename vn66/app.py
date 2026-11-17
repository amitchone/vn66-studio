"""VN66 Studio: local web UI + device manager. Standard library only."""
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import protocol as P

PORT = 47866
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_FILE = os.path.join(ROOT, "ui", "index.html")
WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"
if MAC:
    DATA_DIR = os.path.expanduser("~/Library/Application Support/VN66Studio")
else:
    DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "VN66Studio")
PROFILE_DIR = os.path.join(DATA_DIR, "profiles")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
META_FILE = os.path.join(DATA_DIR, "meta.json")
TOKEN = secrets.token_urlsafe(24)
NAME_RE = re.compile(r"^[\w \-\.\(\)]{1,60}$")


STOCK_IMAGES = ("iot_driver*", "Dukharo Driver.exe")
NO_WINDOW = 0x08000000


def hid_backend():
    """The platform's HID module: enumerate_devices() and HidDevice."""
    if WINDOWS:
        from . import hid_win
        return hid_win
    if MAC:
        from . import hid_mac
        return hid_mac
    raise OSError("VN66 Studio supports Windows and macOS only")


def stock_driver_processes():
    """Names of running stock-driver processes. They poll the keyboard and corrupt our traffic."""
    found = []
    if not WINDOWS:
        return found
    for image in STOCK_IMAGES:
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + image, "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for line in out.splitlines():
            if line.startswith('"'):
                name = line.split('","')[0].strip('"')
                if name not in found:
                    found.append(name)
    return found


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1)
    os.replace(tmp, path)


class Manager:
    """Owns the keyboard connection and a cached copy of everything on it."""

    def __init__(self):
        self.lock = threading.RLock()
        self.kb = None
        self.demo = False
        self.sim = P.SimDevice()
        self.info = {}
        self.config = None
        self.problem = ""
        self.meta = load_json(META_FILE, {"macroNames": {}})
        self.last_ping = time.time()
        self.conflict = []
        self.conflict_checked = 0.0

    def check_conflict(self, force=False):
        if force or time.time() - self.conflict_checked > 6:
            self.conflict = stock_driver_processes()
            self.conflict_checked = time.time()
        return self.conflict

    def stop_stock_driver(self):
        """Only ever called from the button in the UI."""
        for name in self.check_conflict(force=True):
            subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True, timeout=15, creationflags=NO_WINDOW)
        time.sleep(1)
        left = self.check_conflict(force=True)
        if left:
            # The stock driver runs as administrator, so ending it needs a Windows permission prompt.
            kills = "; ".join("taskkill /F /IM '%s'" % n for n in left)
            try:
                subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                                "Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden "
                                "-ArgumentList '-NoProfile','-Command',\"%s\"" % kills],
                               capture_output=True, timeout=120, creationflags=NO_WINDOW)
            except (OSError, subprocess.SubprocessError):
                pass
            time.sleep(1)
            left = self.check_conflict(force=True)
        if left:
            raise P.ProtocolError("Could not stop %s. Open Task Manager (Ctrl+Shift+Esc), go to Details, "
                                  "select it and choose End task." % ", ".join(left))

    # -- connection -------------------------------------------------------
    def _find_real(self):
        """Candidate interfaces, best first, and whether only the 2.4G receiver is present."""
        candidates, seen_dongle = [], False
        for d in hid_backend().enumerate_devices():
            if d["usage_page"] == 1 and d["usage"] == 6 and d["feature_len"] == 65:
                if (d["vid"], d["pid"]) in P.USB_IDS:
                    candidates.append(d)
                elif d["vid"] == 0x25A7:
                    seen_dongle = True
        return candidates, seen_dongle

    def poll(self):
        """Called every couple of seconds: connect if possible, notice unplugging."""
        with self.lock:
            if self.demo:
                return
            if self.check_conflict():
                if self.kb is not None:
                    self._drop("")
                self.problem = ("The stock Dukharo driver is running in the background (%s). It talks to the "
                                "keyboard at the same time, which corrupts reads and writes, so VN66 Studio "
                                "will not connect until it is stopped." % ", ".join(self.conflict))
                return
            if self.kb is not None:
                try:
                    present = any(d["path"] == self.kb.dev.path for d in hid_backend().enumerate_devices())
                except OSError:
                    present = True
                if not present:
                    self._drop("Keyboard disconnected.")
                return
            try:
                found, dongle = self._find_real()
            except OSError as e:
                self.problem = "Could not list USB devices: %s" % e
                return
            if not found:
                self.problem = ("Keyboard is on its 2.4G receiver. Settings can only be changed over the USB "
                                "cable: plug it in and press Fn+T.") if dongle else                                "No VN66 found. Plug in the USB cable and press Fn+T for wired mode."
                return
            for candidate in found:                  # one on Windows; macOS may offer several interfaces
                try:
                    dev = hid_backend().HidDevice(candidate["path"])
                except OSError as e:
                    self.problem = "Found the keyboard but could not open it: %s" % e
                    continue
                try:
                    self._attach(dev, "USB")
                    return
                except (OSError, P.ProtocolError) as e:
                    dev.close()
                    self.kb = None
                    self.problem = "Found the keyboard but could not read it: %s" % e

    def _attach(self, dev, link):
        kb = P.Keyboard(dev, fast=isinstance(dev, P.SimDevice))
        dev_id = kb.device_id()
        if dev_id not in P.DEVICE_IDS:
            raise P.ProtocolError("this is not a VN66 (device id %d)" % dev_id)
        self.kb = kb
        self.info = {"firmware": kb.firmware_version(), "link": link, "deviceId": dev_id}
        kb.read_profile()
        self.problem = ""
        self.read_all()
        if not any("first-connect" in f for f in os.listdir(BACKUP_DIR)):
            self.backup("first-connect")

    def _drop(self, why):
        if self.kb:
            try:
                self.kb.dev.close()
            except OSError:
                pass
        self.kb = None
        self.config = None
        self.problem = why

    def set_demo(self, on):
        with self.lock:
            self._drop("")
            self.demo = bool(on)
            if self.demo:
                self._attach(self.sim, "Demo")

    # -- reading ----------------------------------------------------------
    def read_all(self):
        kb = self.kb
        matrix = kb.get_keymap()
        fn = kb.get_fn()
        bits = kb.get_option_bits()
        raw = kb.get_perkey()
        perkey = {}
        for idx in range(P.MATRIX_ENTRIES):
            perkey[str(idx)] = P.rgb_to_hex(raw[idx * 3:idx * 3 + 3])
        macros = {}
        for slot in range(P.MACRO_SLOTS):
            m = kb.get_macro(slot)
            if m:
                m["name"] = self.meta["macroNames"].get(str(slot), "Macro %d" % (slot + 1))
                macros[str(slot)] = m
        self.config = {
            "keymap": [list(matrix[i:i + 4]) for i in range(0, P.MATRIX_BYTES, 4)],
            "fnmap": [list(fn[i:i + 4]) for i in range(0, P.MATRIX_BYTES, 4)],
            "light": kb.get_light(),
            "perkey": perkey,
            "macros": macros,
            "rate": kb.get_rate(),
            "winLock": bool(bits & P.OPT_WIN_LOCK),
            "wasdSwap": bool(bits & P.OPT_WASD_SWAP),
            "macLayout": bool(bits & P.OPT_MAC_LAYOUT),
        }

    def backup(self, label):
        if self.demo:                                # never mix simulated data into real backups
            return None
        name = "%s-%s.json" % (time.strftime("%Y%m%d-%H%M%S"), label)
        save_json(os.path.join(BACKUP_DIR, name), self.config)
        return name

    def state(self):
        with self.lock:
            return {
                "connected": self.kb is not None, "demo": self.demo, "info": self.info,
                "problem": self.problem, "config": self.config, "conflict": [] if self.demo else self.conflict,
                "defaultKeymap": [list(self._default()[i:i + 4]) for i in range(0, P.MATRIX_BYTES, 4)],
                "defaultFnmap": [list(P.DEFAULT_FN[i:i + 4]) for i in range(0, P.MATRIX_BYTES, 4)],
                "knob": P.knob_indices(self.info.get("deviceId")),
                "modes": [{"id": m[0], "key": m[1], "label": m[2], "speed": m[3], "colour": m[4],
                           "options": m[5]} for m in P.LIGHT_MODES],
                "macroSlots": P.MACRO_SLOTS, "macroMax": P.MACRO_MAX_USED, "dataDir": DATA_DIR,
            }

    def _default(self):
        return P.default_matrix(self.info.get("deviceId"))

    # -- writing ----------------------------------------------------------
    def _need(self):
        if self.kb is None:
            raise P.ProtocolError("keyboard is not connected")
        return self.kb

    def _guard(self, fn):
        """Run a device operation; a transport failure drops the connection."""
        with self.lock:
            if not self.demo and self.check_conflict(force=True):
                raise P.ProtocolError("The stock Dukharo driver started in the background. Stop it before writing.")
            try:
                return fn(self._need())
            except OSError as e:
                self._drop("Lost the keyboard while writing: %s" % e)
                raise P.ProtocolError("lost the keyboard while writing") from e

    def write_keymap(self, keymap):
        if len(keymap) != P.MATRIX_ENTRIES or any(len(e) != 4 for e in keymap):
            raise P.ProtocolError("bad key map")
        data = bytes(b & 255 for e in keymap for b in e)

        def go(kb):
            kb.set_keymap(data)
            self.config["keymap"] = [list(data[i:i + 4]) for i in range(0, P.MATRIX_BYTES, 4)]
        self._guard(go)

    def write_fnmap(self, fnmap):
        if len(fnmap) != P.MATRIX_ENTRIES or any(len(e) != 4 for e in fnmap):
            raise P.ProtocolError("bad Fn layer")
        data = bytes(b & 255 for e in fnmap for b in e)

        def go(kb):
            kb.set_fn(data)
            self.config["fnmap"] = [list(data[i:i + 4]) for i in range(0, P.MATRIX_BYTES, 4)]
        self._guard(go)

    def write_light(self, light):
        def go(kb):
            kb.set_light(light)
            # no read-back: the keyboard must not be disturbed while it saves
            self.config["light"] = P.decode_light(P.encode_light(light))
        self._guard(go)

    def write_perkey(self, colours):
        data = bytearray(b"\xff" * P.PERKEY_BYTES)
        for idx in range(P.MATRIX_ENTRIES):
            rgb = P.hex_to_rgb(colours.get(str(idx), "#000000"))
            data[idx * 3:idx * 3 + 3] = bytes(rgb)

        def go(kb):
            kb.set_perkey(data)
            self.config["perkey"] = {str(i): P.rgb_to_hex(data[i * 3:i * 3 + 3]) for i in range(P.MATRIX_ENTRIES)}
        self._guard(go)

    def write_macro(self, slot, macro):
        slot = int(slot)
        events = (macro or {}).get("events") or []
        repeat = int((macro or {}).get("repeat") or 1)
        P.encode_macro(repeat, events)          # validate before touching the device

        def go(kb):
            kb.set_macro(slot, repeat, events)
            back = kb.get_macro(slot)
            if events and back is None:
                raise P.ProtocolError("the keyboard did not store the macro")
            if back:
                name = str((macro or {}).get("name") or "Macro %d" % (slot + 1))[:40]
                self.meta["macroNames"][str(slot)] = name
                back["name"] = name
                self.config["macros"][str(slot)] = back
            else:
                self.config["macros"].pop(str(slot), None)
                self.meta["macroNames"].pop(str(slot), None)
            save_json(META_FILE, self.meta)
        self._guard(go)

    def write_settings(self, s):
        def go(kb):
            if "rate" in s and s["rate"] != self.config["rate"]:
                kb.set_rate(int(s["rate"]))
                self.config["rate"] = kb.get_rate()
            if any(k in s for k in ("winLock", "wasdSwap", "macLayout")):
                bits = kb.get_option_bits()
                for key, flag in (("winLock", P.OPT_WIN_LOCK), ("wasdSwap", P.OPT_WASD_SWAP),
                                  ("macLayout", P.OPT_MAC_LAYOUT)):
                    if key in s:
                        bits = (bits | flag) if s[key] else (bits & ~flag)
                kb.set_option_bits(bits)
                bits = kb.get_option_bits()
                self.config["winLock"] = bool(bits & P.OPT_WIN_LOCK)
                self.config["wasdSwap"] = bool(bits & P.OPT_WASD_SWAP)
                self.config["macLayout"] = bool(bits & P.OPT_MAC_LAYOUT)
        self._guard(go)

    def apply_all(self, cfg):
        """Write a whole saved profile to the keyboard."""
        with self.lock:
            self._need()
            self.backup("before-apply")
            for slot in range(P.MACRO_SLOTS):
                wanted = cfg.get("macros", {}).get(str(slot))
                if wanted or str(slot) in self.config["macros"]:
                    self.write_macro(slot, wanted)
            if "keymap" in cfg:
                self.write_keymap(cfg["keymap"])
            if "fnmap" in cfg:
                self.write_fnmap(cfg["fnmap"])
            if "perkey" in cfg:
                self.write_perkey(cfg["perkey"])
            if "light" in cfg:
                self.write_light(cfg["light"])
            self.write_settings({k: cfg[k] for k in ("rate", "winLock", "wasdSwap", "macLayout") if cfg.get(k) is not None})

    def factory_reset(self):
        def go(kb):
            self.backup("before-reset")
            kb.factory_reset()
            self.read_all()
        self._guard(go)

    def refresh(self):
        self._guard(lambda kb: self.read_all())


MGR = Manager()


# ------------------------------------------------------------------ HTTP

def profile_path(name):
    if not NAME_RE.match(name or ""):
        raise P.ProtocolError("profile names can use letters, numbers, spaces and - . ( )")
    return os.path.join(PROFILE_DIR, name + ".json")


def handle_api(path, body):
    MGR.last_ping = time.time()
    if path == "/api/state":
        return MGR.state()
    if path == "/api/demo":
        MGR.set_demo(body.get("on"))
        if not body.get("on"):
            MGR.poll()
    elif path == "/api/stopStock":
        MGR.stop_stock_driver()
        MGR.poll()
    elif path == "/api/refresh":
        MGR.refresh()
    elif path == "/api/keymap":
        MGR.write_keymap(body["keymap"])
    elif path == "/api/fnmap":
        MGR.write_fnmap(body["fnmap"])
    elif path == "/api/light":
        MGR.write_light(body["light"])
    elif path == "/api/perkey":
        MGR.write_perkey(body["colours"])
    elif path == "/api/macro":
        MGR.write_macro(body["slot"], body.get("macro"))
    elif path == "/api/settings":
        MGR.write_settings(body)
    elif path == "/api/reset":
        MGR.factory_reset()
    elif path == "/api/applyAll":
        MGR.apply_all(body["config"])
    elif path == "/api/profiles":
        names = sorted(f[:-5] for f in os.listdir(PROFILE_DIR) if f.endswith(".json"))
        backups = sorted((f[:-5] for f in os.listdir(BACKUP_DIR) if f.endswith(".json")), reverse=True)
        return {"profiles": names, "backups": backups[:30]}
    elif path == "/api/profile/save":
        with MGR.lock:
            if MGR.config is None:
                raise P.ProtocolError("nothing to save: no keyboard connected")
            save_json(profile_path(body["name"]), MGR.config)
    elif path == "/api/profile/load":
        folder = BACKUP_DIR if body.get("backup") else PROFILE_DIR
        profile_path(body["name"])
        cfg = load_json(os.path.join(folder, body["name"] + ".json"), None)
        if not isinstance(cfg, dict):
            raise P.ProtocolError("could not read that profile")
        return {"config": cfg}
    elif path == "/api/profile/delete":
        os.remove(profile_path(body["name"]))
    elif path == "/api/ping":
        MGR.last_ping = time.time()
        return {"ok": True}
    else:
        return None
    return MGR.state()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        return self.headers.get("Host", "") in ("127.0.0.1:%d" % PORT, "localhost:%d" % PORT)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        if self.path in ("/", "/index.html"):
            with open(UI_FILE, "rb") as f:
                page = f.read().replace(b"__TOKEN__", TOKEN.encode())
            return self._send(200, page, "text/html; charset=utf-8")
        if self.path == "/api/alive":
            return self._send(200, {"app": "vn66-studio"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Token") != TOKEN:
            return self._send(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            result = handle_api(self.path, body)
            if result is None:
                return self._send(404, {"error": "not found"})
            self._send(200, result)
        except (P.ProtocolError, KeyError, ValueError, TypeError, OSError) as e:
            self._send(400, {"error": str(e) or e.__class__.__name__, "state": MGR.state()})


def poll_loop():
    while True:
        try:
            MGR.poll()
        except Exception as e:                       # keep the poller alive whatever happens
            MGR.problem = "Unexpected error: %s" % e
        time.sleep(2)


def find_browser():
    candidates = []
    if MAC:
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                      "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidates.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
            candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return shutil.which("msedge") or shutil.which("chrome")


def open_window(url):
    """Open the UI as a chromeless app window; returns the process, or None if a normal tab was used."""
    exe = find_browser()
    if exe:
        return subprocess.Popen([exe, "--app=" + url, "--user-data-dir=" + os.path.join(DATA_DIR, "window"),
                                 "--no-first-run", "--no-default-browser-check", "--window-size=1240,860"])
    webbrowser.open(url)
    return None


def main():
    for d in (PROFILE_DIR, BACKUP_DIR):
        os.makedirs(d, exist_ok=True)
    url = "http://127.0.0.1:%d/" % PORT
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        try:                                         # already running? just show its window
            with urllib.request.urlopen(url + "api/alive", timeout=2) as r:
                if b"vn66-studio" in r.read():
                    open_window(url)
                    return 0
        except (OSError, socket.timeout):
            pass
        print("Port %d is in use by another program." % PORT)
        return 1
    if "--demo" in sys.argv:
        MGR.set_demo(True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=poll_loop, daemon=True).start()
    if "--no-window" in sys.argv:
        print(url)
        while True:
            time.sleep(3600)
    started = time.time()
    proc = open_window(url)
    if proc is not None:
        proc.wait()
        if time.time() - started > 8:                # the window itself was closed
            return 0
        # otherwise the browser handed off to another process: rely on the page's heartbeat
    while time.time() - MGR.last_ping < 150:
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
