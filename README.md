# VN66 Studio

A small replacement for the stock "Dukharo Driver" app for the Dukharo VN66 keyboard.
Python standard library only; nothing to install.

## Run

Windows, Python 3.10+. Double-click `VN66 Studio.cmd`, or run `python -m vn66.app`.
Add `--demo` to start with a simulated keyboard.

The keyboard only accepts settings over the USB cable: plug it in and press Fn+T.
Everything is stored in the keyboard, so it keeps working over 2.4G / Bluetooth afterwards.

The stock driver's background service (`iot_driver_*.exe`) talks to the keyboard at the same time
and corrupts traffic, so the app will not connect while it is running; it offers to stop it.

## What it does

- Keys: remap any key and the knob (turn left / press / turn right) to a key, modifier + key,
  media / system function, mouse button, macro, Fn, or nothing.
- Fn layer: change what each key does while Fn is held, including the keyboard's own functions
  (wireless mode switching, lighting controls).
- Lighting: 16 effects with brightness, speed, direction, rainbow or single colour, plus per-key colours.
- Macros: 20 slots stored on the keyboard; record or build them step by step.
- Settings: polling rate, Windows-key lock, WASD / arrow swap, Mac layout (Alt / Win swap), factory reset.
- Profiles: save everything on the keyboard to a file, write it back later, import / export.
  Automatic backups are taken on first connect and before every profile write or reset.

Not included: firmware updates and the music-reactive lighting modes.

## Hardware notes

Developed against a VN66 that identifies as USB `3151:4003`, device id 282, firmware 774.
The older revision (`0461:4002`, device id 224) is recognised but untested.

After any write that is saved to flash the keyboard must be left alone (about 1 s for settings,
2-3 s for key tables). Talking to it during that window hangs its USB control channel for up to
90 s, so every write books a quiet period before the next report is sent.

## Layout

- `vn66/hid_win.py`   Windows HID access through ctypes
- `vn66/protocol.py`  the keyboard's feature-report protocol, plus a simulator
- `vn66/app.py`       local server (127.0.0.1 only) and device manager
- `ui/index.html`     the interface
- `tests/`            `python tests/test_protocol.py`

Profiles and backups live in `%APPDATA%\VN66Studio`.

## Licence

0BSD: use it for anything, no conditions. See `LICENSE`.

Unofficial; not affiliated with Dukharo.
