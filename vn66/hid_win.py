"""Minimal Windows HID access via ctypes (no third-party packages).

The VN66 exposes its configuration channel as 65-byte feature reports on the
*keyboard* top-level collection. Windows owns keyboard collections exclusively
for read/write, so the handle is opened with zero desired access, which still
permits HidD_SetFeature / HidD_GetFeature.
"""
import ctypes
import ctypes.wintypes as wt
from ctypes import POINTER, Structure, byref, c_ubyte, c_ulong, c_ushort, c_void_p, c_wchar, sizeof

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
INVALID_HANDLE_VALUE = c_void_p(-1).value
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
HIDP_STATUS_SUCCESS = 0x00110000


class GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(Structure):
    _fields_ = [("cbSize", c_ulong), ("InterfaceClassGuid", GUID), ("Flags", c_ulong), ("Reserved", c_void_p)]


class HIDD_ATTRIBUTES(Structure):
    _fields_ = [("Size", c_ulong), ("VendorID", c_ushort), ("ProductID", c_ushort), ("VersionNumber", c_ushort)]


class HIDP_CAPS(Structure):
    _fields_ = [
        ("Usage", c_ushort), ("UsagePage", c_ushort),
        ("InputReportByteLength", c_ushort), ("OutputReportByteLength", c_ushort),
        ("FeatureReportByteLength", c_ushort), ("Reserved", c_ushort * 17),
        ("NumberLinkCollectionNodes", c_ushort), ("NumberInputButtonCaps", c_ushort),
        ("NumberInputValueCaps", c_ushort), ("NumberInputDataIndices", c_ushort),
        ("NumberOutputButtonCaps", c_ushort), ("NumberOutputValueCaps", c_ushort),
        ("NumberOutputDataIndices", c_ushort), ("NumberFeatureButtonCaps", c_ushort),
        ("NumberFeatureValueCaps", c_ushort), ("NumberFeatureDataIndices", c_ushort),
    ]


setupapi.SetupDiGetClassDevsW.restype = c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [POINTER(GUID), c_void_p, c_void_p, c_ulong]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [c_void_p, c_void_p, POINTER(GUID), c_ulong,
                                                 POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [c_void_p, POINTER(SP_DEVICE_INTERFACE_DATA), c_void_p,
                                                      c_ulong, POINTER(c_ulong), c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [c_void_p]
kernel32.CreateFileW.restype = c_void_p
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, c_ulong, c_ulong, c_void_p, c_ulong, c_ulong, c_void_p]
kernel32.CloseHandle.argtypes = [c_void_p]
hid.HidD_GetHidGuid.argtypes = [POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [c_void_p, POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wt.BOOLEAN
hid.HidD_GetPreparsedData.argtypes = [c_void_p, POINTER(c_void_p)]
hid.HidD_GetPreparsedData.restype = wt.BOOLEAN
hid.HidD_FreePreparsedData.argtypes = [c_void_p]
hid.HidP_GetCaps.argtypes = [c_void_p, POINTER(HIDP_CAPS)]
hid.HidD_SetFeature.argtypes = [c_void_p, c_void_p, c_ulong]
hid.HidD_SetFeature.restype = wt.BOOLEAN
hid.HidD_GetFeature.argtypes = [c_void_p, c_void_p, c_ulong]
hid.HidD_GetFeature.restype = wt.BOOLEAN
hid.HidD_GetProductString.argtypes = [c_void_p, c_void_p, c_ulong]
hid.HidD_GetProductString.restype = wt.BOOLEAN


def _open(path):
    h = kernel32.CreateFileW(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    return None if h in (None, INVALID_HANDLE_VALUE) else h


def enumerate_devices():
    """Return a list of dicts describing every present HID collection."""
    guid = GUID()
    hid.HidD_GetHidGuid(byref(guid))
    info = setupapi.SetupDiGetClassDevsW(byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if info in (None, INVALID_HANDLE_VALUE):
        return []
    out = []
    try:
        idx = 0
        while True:
            ifd = SP_DEVICE_INTERFACE_DATA()
            ifd.cbSize = sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(info, None, byref(guid), idx, byref(ifd)):
                break
            idx += 1
            need = c_ulong(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(info, byref(ifd), None, 0, byref(need), None)
            if not need.value:
                continue
            buf = ctypes.create_string_buffer(need.value)
            # cbSize of SP_DEVICE_INTERFACE_DETAIL_DATA_W: 8 on 64-bit, 6 on 32-bit
            ctypes.memmove(buf, byref(c_ulong(8 if sizeof(c_void_p) == 8 else 6)), 4)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(info, byref(ifd), buf, need, None, None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            h = _open(path)
            if not h:
                continue
            try:
                attr = HIDD_ATTRIBUTES()
                attr.Size = sizeof(HIDD_ATTRIBUTES)
                if not hid.HidD_GetAttributes(h, byref(attr)):
                    continue
                entry = {"path": path, "vid": attr.VendorID, "pid": attr.ProductID,
                         "version": attr.VersionNumber, "usage": 0, "usage_page": 0,
                         "feature_len": 0, "input_len": 0, "output_len": 0, "product": ""}
                pp = c_void_p()
                if hid.HidD_GetPreparsedData(h, byref(pp)):
                    caps = HIDP_CAPS()
                    if hid.HidP_GetCaps(pp, byref(caps)) == HIDP_STATUS_SUCCESS:
                        entry.update(usage=caps.Usage, usage_page=caps.UsagePage,
                                     feature_len=caps.FeatureReportByteLength,
                                     input_len=caps.InputReportByteLength,
                                     output_len=caps.OutputReportByteLength)
                    hid.HidD_FreePreparsedData(pp)
                # No HidD_GetProductString here: it sends a request to the device, and this
                # runs every couple of seconds while the keyboard may be busy saving.
                out.append(entry)
            finally:
                kernel32.CloseHandle(h)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info)
    return out


class HidDevice:
    """A handle on one HID collection, used for feature reports only."""

    def __init__(self, path, feature_len=65):
        self.path = path
        self.feature_len = feature_len
        self.handle = _open(path)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "could not open HID device")

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def set_feature(self, payload):
        """Send `payload` (<= feature_len-1 bytes) as a feature report with report id 0."""
        data = bytes([0]) + bytes(payload)
        data = data.ljust(self.feature_len, b"\0")[: self.feature_len]
        buf = ctypes.create_string_buffer(data, self.feature_len)
        if not hid.HidD_SetFeature(self.handle, buf, self.feature_len):
            raise OSError(ctypes.get_last_error(), "HidD_SetFeature failed")

    def get_feature(self):
        """Read a feature report; returns the payload without the report id byte."""
        buf = ctypes.create_string_buffer(self.feature_len)
        if not hid.HidD_GetFeature(self.handle, buf, self.feature_len):
            raise OSError(ctypes.get_last_error(), "HidD_GetFeature failed")
        return bytes(buf.raw[1:])


if __name__ == "__main__":
    for d in enumerate_devices():
        print(f"{d['vid']:04X}:{d['pid']:04X} usage {d['usage_page']:04X}/{d['usage']:04X} "
              f"feat={d['feature_len']} in={d['input_len']} out={d['output_len']} {d['product']!r}")
