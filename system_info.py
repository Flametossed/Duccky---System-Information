"""System information collector — Windows primary, graceful fallback elsewhere."""

import psutil
import platform
import socket as _socket
import threading
import ctypes
from ctypes import wintypes
from datetime import datetime

try:
    import wmi as _wmilib
    WMI_AVAILABLE = True
except Exception:
    WMI_AVAILABLE = False

try:
    import pythoncom as _pythoncom
    PYTHONCOM_AVAILABLE = True
except Exception:
    PYTHONCOM_AVAILABLE = False

try:
    import cpuinfo as _cpuinfo
    CPUINFO_AVAILABLE = True
except ImportError:
    CPUINFO_AVAILABLE = False


# WMI uses COM, which is per-thread. Cache one WMI connection per thread.
_thread_local = threading.local()


def _wmi():
    """Return WMI handle for current thread, init COM if needed."""
    if not WMI_AVAILABLE:
        return None
    cached = getattr(_thread_local, "wmi", None)
    if cached is not None:
        return cached
    if PYTHONCOM_AVAILABLE:
        try:
            _pythoncom.CoInitialize()
        except Exception:
            pass
    try:
        _thread_local.wmi = _wmilib.WMI()
    except Exception:
        _thread_local.wmi = None
    return _thread_local.wmi


# ── Utilities ─────────────────────────────────────────────────────────────────

def bytes_to_human(n, precision=1):
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.{precision}f} {unit}"
        n /= 1024.0
    return f"{n:.{precision}f} PB"


def _wmi_date(d):
    if not d or len(d) < 8:
        return ""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _uptime_str():
    sec = datetime.now().timestamp() - psutil.boot_time()
    d = int(sec // 86400)
    h = int((sec % 86400) // 3600)
    m = int((sec % 3600) // 60)
    return f"{d}d {h}h {m}m" if d else f"{h}h {m}m"


# ── Static collectors ─────────────────────────────────────────────────────────

def get_os_info():
    info = dict(
        caption=f"{platform.system()} {platform.release()}",
        version=platform.version(),
        architecture=platform.machine(),
        hostname=_socket.gethostname(),
        uptime=_uptime_str(),
        build="",
        install_date="",
    )
    if WMI_AVAILABLE:
        try:
            for o in _wmi().Win32_OperatingSystem():
                info["caption"] = (o.Caption or "").strip()
                info["version"] = o.Version or ""
                info["build"] = o.BuildNumber or ""
                info["architecture"] = (o.OSArchitecture or "").strip()
                info["install_date"] = _wmi_date(o.InstallDate)
                break
        except Exception:
            pass
    return info


def get_cpu_info():
    info = dict(
        name=platform.processor() or "Unknown Processor",
        manufacturer="",
        socket="",
        cores_physical=psutil.cpu_count(logical=False) or 0,
        cores_logical=psutil.cpu_count(logical=True) or 0,
        freq_max_mhz=0,
        l2_cache_kb=None,
        l3_cache_kb=None,
    )
    freq = psutil.cpu_freq()
    if freq:
        info["freq_max_mhz"] = freq.max or freq.current or 0

    if WMI_AVAILABLE:
        try:
            for c in _wmi().Win32_Processor():
                if c.Name:
                    info["name"] = c.Name.strip()
                info["manufacturer"] = (c.Manufacturer or "").strip()
                info["socket"] = (c.SocketDesignation or "").strip()
                if c.MaxClockSpeed:
                    info["freq_max_mhz"] = float(c.MaxClockSpeed)
                if c.L2CacheSize:
                    info["l2_cache_kb"] = c.L2CacheSize
                if c.L3CacheSize:
                    info["l3_cache_kb"] = c.L3CacheSize
                break
        except Exception:
            pass

    if CPUINFO_AVAILABLE:
        try:
            ci = _cpuinfo.get_cpu_info()
            if ci.get("brand_raw"):
                info["name"] = ci["brand_raw"]
        except Exception:
            pass

    return info


def get_cpu_live():
    per_core = psutil.cpu_percent(interval=0.1, percpu=True)
    overall = sum(per_core) / len(per_core) if per_core else 0.0
    temp = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
                if key in temps and temps[key]:
                    temp = temps[key][0].current
                    break
            if temp is None:
                for entries in temps.values():
                    if entries:
                        temp = entries[0].current
                        break
    except Exception:
        pass
    return dict(per_core=per_core, overall=overall, temp=temp)


def get_ram_info():
    vm = psutil.virtual_memory()
    info = dict(
        total=vm.total, used=vm.used, available=vm.available, percent=vm.percent,
        memory_type="", speed_mhz=None, channels="", modules=[],
    )
    if WMI_AVAILABLE:
        type_map = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
        try:
            for m in _wmi().Win32_PhysicalMemory():
                t_code = m.MemoryType or 0
                t_str = type_map.get(t_code, f"Type {t_code}" if t_code else "")
                info["modules"].append(dict(
                    slot=(m.DeviceLocator or "").strip(),
                    capacity=int(m.Capacity) if m.Capacity else 0,
                    speed=m.Speed,
                    type_str=t_str,
                    manufacturer=(m.Manufacturer or "").strip(),
                    part_number=(m.PartNumber or "").strip(),
                ))
                if m.Speed and not info["speed_mhz"]:
                    info["speed_mhz"] = m.Speed
                if not info["memory_type"] and t_str:
                    info["memory_type"] = t_str
        except Exception:
            pass
    n = len(info["modules"])
    info["channels"] = ("Quad-Channel" if n >= 4 else
                        "Dual-Channel" if n >= 2 else
                        "Single-Channel" if n == 1 else "")
    return info


def get_motherboard_info():
    info = dict(manufacturer="", product="", version="",
                bios_vendor="", bios_version="", bios_date="")
    if WMI_AVAILABLE:
        try:
            for b in _wmi().Win32_BaseBoard():
                info["manufacturer"] = (b.Manufacturer or "").strip()
                info["product"] = (b.Product or "").strip()
                info["version"] = (b.Version or "").strip()
                break
        except Exception:
            pass
        try:
            for b in _wmi().Win32_BIOS():
                info["bios_vendor"] = (b.Manufacturer or "").strip()
                info["bios_version"] = (b.SMBIOSBIOSVersion or b.Version or "").strip()
                info["bios_date"] = _wmi_date(b.ReleaseDate)
                break
        except Exception:
            pass
    return info


# ── Display / Monitor detection (Windows) ─────────────────────────────────────

class _DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName",         wintypes.WCHAR * 32),
        ("dmSpecVersion",        wintypes.WORD),
        ("dmDriverVersion",      wintypes.WORD),
        ("dmSize",               wintypes.WORD),
        ("dmDriverExtra",        wintypes.WORD),
        ("dmFields",             wintypes.DWORD),
        ("dmPositionX",          wintypes.LONG),
        ("dmPositionY",          wintypes.LONG),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor",              wintypes.SHORT),
        ("dmDuplex",             wintypes.SHORT),
        ("dmYResolution",        wintypes.SHORT),
        ("dmTTOption",           wintypes.SHORT),
        ("dmCollate",            wintypes.SHORT),
        ("dmFormName",           wintypes.WCHAR * 32),
        ("dmLogPixels",          wintypes.WORD),
        ("dmBitsPerPel",         wintypes.DWORD),
        ("dmPelsWidth",          wintypes.DWORD),
        ("dmPelsHeight",         wintypes.DWORD),
        ("dmDisplayFlags",       wintypes.DWORD),
        ("dmDisplayFrequency",   wintypes.DWORD),
        ("dmICMMethod",          wintypes.DWORD),
        ("dmICMIntent",          wintypes.DWORD),
        ("dmMediaType",          wintypes.DWORD),
        ("dmDitherType",         wintypes.DWORD),
        ("dmReserved1",          wintypes.DWORD),
        ("dmReserved2",          wintypes.DWORD),
        ("dmPanningWidth",       wintypes.DWORD),
        ("dmPanningHeight",      wintypes.DWORD),
    ]


class _DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb",           wintypes.DWORD),
        ("DeviceName",   wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags",   wintypes.DWORD),
        ("DeviceID",     wintypes.WCHAR * 128),
        ("DeviceKey",    wintypes.WCHAR * 128),
    ]


_DISPLAY_DEVICE_ATTACHED   = 0x00000001
_DISPLAY_DEVICE_PRIMARY    = 0x00000004
_DISPLAY_DEVICE_ACTIVE     = 0x00000001  # alias for monitor active


def _monitor_edid_key(s: str) -> str:
    """Extract EDID 7-char vendor+product key (e.g. 'LGE5B14') from device id."""
    if not s:
        return ""
    norm = s.replace("\\", "#")
    parts = norm.split("#")
    return parts[1].upper() if len(parts) >= 2 else ""


def _get_primary_display():
    """Primary display only — kept for backward compatibility."""
    displays = _get_all_displays()
    for d in displays:
        if d.get("primary"):
            return d
    return displays[0] if displays else None


def _get_all_displays():
    """Enumerate every active physical display: resolution, refresh, monitor id."""
    out = []
    try:
        u32 = ctypes.windll.user32
        adapter = _DISPLAY_DEVICEW()
        adapter.cb = ctypes.sizeof(_DISPLAY_DEVICEW)

        i = 0
        while u32.EnumDisplayDevicesW(None, i, ctypes.byref(adapter), 0):
            if adapter.StateFlags & _DISPLAY_DEVICE_ATTACHED:
                is_primary = bool(adapter.StateFlags & _DISPLAY_DEVICE_PRIMARY)
                # Pull resolution / refresh for this adapter
                dm = _DEVMODEW()
                dm.dmSize = ctypes.sizeof(_DEVMODEW)
                if u32.EnumDisplaySettingsW(adapter.DeviceName, -1, ctypes.byref(dm)):
                    # Find attached monitor for friendly id
                    mon = _DISPLAY_DEVICEW()
                    mon.cb = ctypes.sizeof(_DISPLAY_DEVICEW)
                    monitor_device_id = ""
                    monitor_string = ""
                    j = 0
                    while u32.EnumDisplayDevicesW(adapter.DeviceName, j,
                                                   ctypes.byref(mon), 0):
                        if mon.StateFlags & _DISPLAY_DEVICE_ATTACHED:
                            monitor_device_id = mon.DeviceID
                            monitor_string = mon.DeviceString
                            break
                        j += 1

                    out.append(dict(
                        width=int(dm.dmPelsWidth),
                        height=int(dm.dmPelsHeight),
                        refresh=int(dm.dmDisplayFrequency),
                        primary=is_primary,
                        adapter_name=adapter.DeviceString,
                        monitor_device_id=monitor_device_id,
                        monitor_string=monitor_string,
                        edid_key=_monitor_edid_key(monitor_device_id),
                    ))
            i += 1
    except Exception:
        pass

    # Primary first
    out.sort(key=lambda d: not d.get("primary"))
    return out


# 3-letter EDID PNP IDs → manufacturer
_EDID_VENDOR = {
    "AAC": "AcerView", "ACI": "Asus", "ACR": "Acer", "AOC": "AOC",
    "APP": "Apple",  "ASU": "Asus", "AUS": "Asus", "BNQ": "BenQ",
    "CMN": "Chimei", "CMO": "Chi Mei", "CPQ": "Compaq", "CTX": "CTX",
    "DEL": "Dell",   "ENC": "Eizo", "EPI": "Envision", "FUS": "Fujitsu Siemens",
    "GSM": "LG",     "GWY": "Gateway", "HEI": "Hyundai", "HIQ": "Hyundai ImageQuest",
    "HSD": "Hannspree", "HTC": "Hitachi/Nissei", "HWP": "HP", "IBM": "IBM",
    "ICL": "Fujitsu ICL", "IVM": "Iiyama", "KDS": "Korea Data Systems", "LEN": "Lenovo",
    "LGD": "LG Display", "LPL": "LG Philips", "MAX": "Belinea",
    "MEI": "Panasonic", "MEL": "Mitsubishi", "MIR": "miro", "MTC": "Mitac",
    "NEC": "NEC",    "NOK": "Nokia", "NVD": "Nvidia", "OQI": "Optiquest",
    "PHL": "Philips", "REL": "Relisys", "SAM": "Samsung", "SAN": "Samsung",
    "SBI": "Smarttech", "SEC": "Seiko Epson", "SHP": "Sharp",
    "SNY": "Sony",   "SRC": "Shamrock", "STN": "Samtron", "TAT": "Tatung",
    "TOS": "Toshiba", "TSB": "Toshiba", "VSC": "ViewSonic", "ZCM": "Zenith",
    "MSI": "MSI",    "GBT": "Gigabyte", "ASR": "ASRock",
}


def _decode_wmi_chars(arr):
    """Decode UInt16 char array from WMI to string."""
    if not arr:
        return ""
    try:
        return "".join(chr(c) for c in arr if c).strip()
    except Exception:
        return ""


def _get_monitors():
    """Returns list of monitor info dicts via WmiMonitorID, keyed by EDID key."""
    monitors = []
    if not WMI_AVAILABLE:
        return monitors
    if PYTHONCOM_AVAILABLE:
        try:
            _pythoncom.CoInitialize()
        except Exception:
            pass
    try:
        wmi_monitor = _wmilib.WMI(namespace="root\\wmi")
        for m in wmi_monitor.WmiMonitorID():
            name = _decode_wmi_chars(getattr(m, "UserFriendlyName", None))
            product = _decode_wmi_chars(getattr(m, "ProductCodeID", None))
            mfr_code = _decode_wmi_chars(getattr(m, "ManufacturerName", None))
            mfr = _EDID_VENDOR.get(mfr_code, mfr_code) if mfr_code else ""
            label = name or product
            if mfr and label and mfr.lower() not in label.lower():
                label = f"{mfr} {label}"
            instance = getattr(m, "InstanceName", "") or ""
            monitors.append(dict(
                name=label or "Generic Display",
                manufacturer=mfr,
                model=product,
                edid_key=_monitor_edid_key(instance),
            ))
    except Exception:
        pass
    return monitors


def get_displays():
    """Return all active physical displays with monitor model + resolution + refresh."""
    displays = _get_all_displays()
    monitors = _get_monitors()

    # Build EDID-key → monitor name map
    by_key = {m["edid_key"]: m for m in monitors if m.get("edid_key")}

    result = []
    for d in displays:
        mon = by_key.get(d.get("edid_key", ""))
        name = (mon["name"] if mon else d.get("monitor_string")) or "Generic Display"
        result.append(dict(
            name=name,
            primary=d.get("primary", False),
            width=d["width"],
            height=d["height"],
            refresh=d["refresh"],
            adapter_name=d.get("adapter_name", ""),
        ))
    return result


def get_gpu_info():
    gpus = []
    if WMI_AVAILABLE:
        try:
            for g in _wmi().Win32_VideoController():
                name = (g.Name or "").strip()
                if not name:
                    continue
                low = name.lower()
                is_virtual = any(k in low for k in
                                  ("sudomaker", "virtual", "remote", "idd"))
                vram = g.AdapterRAM
                vram_str = bytes_to_human(vram) if (vram and vram > 0) else "N/A"
                gpus.append(dict(
                    name=name,
                    vram=vram_str,
                    driver_version=(g.DriverVersion or "").strip(),
                    driver_date=_wmi_date(g.DriverDate),
                    is_virtual=is_virtual,
                ))
        except Exception:
            pass
    gpus.sort(key=lambda g: g.get("is_virtual", False))
    return gpus


def get_storage_info():
    drives = []
    for part in psutil.disk_partitions(all=False):
        if not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue
        drives.append(dict(
            device=part.device, mountpoint=part.mountpoint, fstype=part.fstype,
            total=usage.total, used=usage.used, free=usage.free,
            percent=usage.percent, model="", drive_type="",
        ))
    if WMI_AVAILABLE:
        try:
            disk_map = {}
            for disk in _wmi().Win32_DiskDrive():
                model = (disk.Model or "").strip()
                is_ssd = any(k in model.upper() for k in ("SSD", "NVME", "SOLID STATE"))
                disk_map[disk.Index] = dict(model=model, drive_type="SSD" if is_ssd else "HDD")
            for dp in _wmi().Win32_DiskPartition():
                try:
                    assoc = _wmi().query(
                        f"ASSOCIATORS OF {{Win32_DiskPartition.DeviceID='{dp.DeviceID}'}} "
                        "WHERE AssocClass=Win32_LogicalDiskToPartition"
                    )
                    for ld in assoc:
                        letter = ld.DeviceID
                        for d in drives:
                            if d["device"].rstrip("\\") == letter or \
                               d["mountpoint"].rstrip("\\") == letter:
                                di = disk_map.get(dp.DiskIndex)
                                if di:
                                    d["model"] = di["model"]
                                    d["drive_type"] = di["drive_type"]
                except Exception:
                    pass
        except Exception:
            pass
    return drives


def get_network_info():
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    adapters = []
    for name, stat in stats.items():
        if not stat.isup:
            continue
        ipv4 = mac = ""
        for addr in addrs.get(name, []):
            if addr.family == _socket.AF_INET:
                ipv4 = addr.address
            elif addr.family == psutil.AF_LINK:
                mac = addr.address
        adapters.append(dict(
            name=name, speed_mbps=stat.speed, mtu=stat.mtu, ipv4=ipv4, mac=mac,
        ))
    return adapters


def get_audio_info():
    devices = []
    if WMI_AVAILABLE:
        try:
            for d in _wmi().Win32_SoundDevice():
                name = (d.Name or "").strip()
                if name:
                    devices.append(dict(
                        name=name,
                        manufacturer=(d.Manufacturer or "").strip(),
                        status=(d.Status or "").strip(),
                    ))
        except Exception:
            pass
    return devices


def collect_all():
    return dict(
        os=get_os_info(),
        cpu=get_cpu_info(),
        ram=get_ram_info(),
        motherboard=get_motherboard_info(),
        gpu=get_gpu_info(),
        displays=get_displays(),
        storage=get_storage_info(),
        network=get_network_info(),
        audio=get_audio_info(),
    )
