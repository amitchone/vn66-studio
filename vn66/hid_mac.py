"""macOS HID access through the `hidapi` package (pip3 install hidapi).

Presents the same two things as hid_win: enumerate_devices() and HidDevice.
macOS does not report feature-report sizes, so every keyboard-usage interface of a
matching device is offered as a candidate (interface 0 first) and the app keeps the
one that answers the identification query.
"""
try:
    import hid
except ImportError:                                   # reported to the user by the app
    hid = None

FEATURE_LEN = 65
MISSING = "The hidapi package is not installed. Run: pip3 install hidapi"


def _need():
    if hid is None or not hasattr(hid, "device"):
        raise OSError(MISSING)


def enumerate_devices():
    _need()
    out = []
    try:
        found = hid.enumerate()
    except Exception as e:                            # hidapi raises several types
        raise OSError("could not list HID devices: %s" % e)
    for d in found:
        out.append({
            "path": d.get("path"), "vid": d.get("vendor_id", 0), "pid": d.get("product_id", 0),
            "version": d.get("release_number", 0),
            "usage": d.get("usage", 0), "usage_page": d.get("usage_page", 0),
            "interface": d.get("interface_number", -1),
            # assumed: the real check is whether the interface answers the protocol
            "feature_len": FEATURE_LEN if (d.get("usage_page"), d.get("usage")) == (1, 6) else 0,
            "input_len": 0, "output_len": 0, "product": d.get("product_string") or "",
        })
    out.sort(key=lambda d: (d["interface"] != 0, d["interface"]))
    return out


class HidDevice:
    def __init__(self, path, feature_len=FEATURE_LEN):
        _need()
        self.path = path
        self.feature_len = feature_len
        self.dev = hid.device()
        try:
            self.dev.open_path(path)
        except Exception as e:
            self.dev = None
            raise OSError("could not open the keyboard (%s). On macOS, allow this app or Terminal under "
                          "System Settings > Privacy & Security > Input Monitoring, then start it again." % e)

    def close(self):
        if self.dev is not None:
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None

    def set_feature(self, payload):
        data = (bytes([0]) + bytes(payload)).ljust(self.feature_len, b"\0")[: self.feature_len]
        try:
            sent = self.dev.send_feature_report(data)
        except Exception as e:
            raise OSError("send_feature_report failed: %s" % e)
        if sent is not None and sent < 0:
            raise OSError("send_feature_report failed")

    def get_feature(self):
        try:
            data = bytes(self.dev.get_feature_report(0, self.feature_len))
        except Exception as e:
            raise OSError("get_feature_report failed: %s" % e)
        if len(data) >= self.feature_len:             # report id byte included
            data = data[1:self.feature_len]
        if len(data) < self.feature_len - 1:
            raise OSError("short feature report (%d bytes)" % len(data))
        return data


if __name__ == "__main__":
    for d in enumerate_devices():
        print("%04X:%04X usage %04X/%04X if=%s %r" % (d["vid"], d["pid"], d["usage_page"], d["usage"],
                                                     d["interface"], d["product"]))
