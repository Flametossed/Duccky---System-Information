"""Duccky — modern system information viewer."""

import os
import threading
import time
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
import psutil
from PIL import Image

import system_info as si
import spec_image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#0a0a12"
SIDEBAR_BG = "#070710"
CARD_BG    = "#13131e"
CARD_HL    = "#1c1c2c"
BORDER     = "#22223a"
TEXT_PRI   = "#e8e8f4"
TEXT_SEC   = "#7878a8"
TEXT_DIM   = "#3c3c5e"
ACCENT_PRI = "#8b7cff"

C = {
    "summary":     "#8b7cff",
    "os":          "#f06292",
    "cpu":         "#ffb74d",
    "ram":         "#64b5f6",
    "motherboard": "#ce93d8",
    "gpu":         "#f48fb1",
    "storage":     "#4db6ac",
    "network":     "#4dd0e1",
    "audio":       "#ffcc80",
}

SECTIONS = [
    ("summary",     "◈",  "Summary"),
    ("os",          "⬚", "Operating System"),
    ("cpu",         "⚡", "CPU"),
    ("ram",         "▦",  "RAM"),
    ("motherboard", "⬡",  "Motherboard"),
    ("gpu",         "▣",  "Graphics"),
    ("storage",     "◎",  "Storage"),
    ("network",     "◉",  "Network"),
    ("audio",       "◔",  "Audio"),
]

F_HEAD     = ("Segoe UI", 11, "bold")
F_BODY     = ("Segoe UI", 10)
F_SMALL    = ("Segoe UI", 9)
F_TITLE    = ("Segoe UI", 18, "bold")
F_BIG      = ("Segoe UI", 22, "bold")
F_BRAND    = ("Segoe UI", 18, "bold")

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_PNG = os.path.join(HERE, "logo.png")
LOGO_ICO = os.path.join(HERE, "logo.ico")


# ──────────────────────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Duccky — System Information")
        self.root.geometry("960x680")
        self.root.minsize(820, 560)
        self.root.configure(fg_color=BG)

        # Window icon
        try:
            if os.path.exists(LOGO_ICO):
                self.root.iconbitmap(LOGO_ICO)
        except Exception:
            pass

        # Logo image for sidebar
        self._logo_img = None
        try:
            if os.path.exists(LOGO_PNG):
                pil = Image.open(LOGO_PNG)
                self._logo_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(40, 40))
        except Exception:
            pass

        self.current_section = "summary"
        self.live_widgets: dict = {}
        self._stop = threading.Event()
        self.data: dict = {}

        self._build_skeleton()
        self._show_loading()
        threading.Thread(target=self._load_data, daemon=True).start()

    # ── Skeleton ──────────────────────────────────────────────────────────────

    def _build_skeleton(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self.root, width=215, fg_color=SIDEBAR_BG, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # ── Brand block (logo + wordmark) ─────────────────────────────────────
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(22, 12))

        if self._logo_img:
            ctk.CTkLabel(brand, image=self._logo_img, text="").pack(side="left", padx=(0, 10))

        title_block = ctk.CTkFrame(brand, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text="DUCCKY", font=F_BRAND,
                     text_color=TEXT_PRI).pack(anchor="w")
        ctk.CTkLabel(title_block, text="System Info", font=F_SMALL,
                     text_color=TEXT_SEC).pack(anchor="w")

        # Divider
        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER).pack(
            fill="x", padx=14, pady=(4, 14))

        # ── Nav buttons ───────────────────────────────────────────────────────
        self.nav_btns: dict[str, dict] = {}
        for key, icon, label in SECTIONS:
            row = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=38)
            row.pack(fill="x", padx=10, pady=2)
            row.pack_propagate(False)

            indicator = ctk.CTkFrame(row, width=3, fg_color="transparent", corner_radius=2)
            indicator.pack(side="left", fill="y")
            indicator.pack_propagate(False)

            btn = ctk.CTkButton(
                row,
                text=f"  {icon}    {label}",
                font=F_BODY, anchor="w",
                fg_color="transparent", hover_color=CARD_HL,
                text_color=TEXT_SEC, height=34, corner_radius=6,
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(side="left", fill="both", expand=True, padx=(6, 0))
            self.nav_btns[key] = {"btn": btn, "indicator": indicator}

        # ── Bottom: action buttons + version ──────────────────────────────────
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 14))

        self.status_lbl = ctk.CTkLabel(
            bottom, text="", font=F_SMALL, text_color=C["storage"], anchor="w")
        self.status_lbl.pack(fill="x", pady=(0, 6))

        ver_row = ctk.CTkFrame(bottom, fg_color="transparent")
        ver_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(ver_row, text="v1.0", font=F_SMALL,
                     text_color=TEXT_DIM).pack(side="left")
        self.update_lbl = ctk.CTkLabel(ver_row, text="", font=F_SMALL,
                                        text_color=TEXT_DIM)
        self.update_lbl.pack(side="right")

        # 3-button row
        btns = ctk.CTkFrame(bottom, fg_color="transparent")
        btns.pack(fill="x")

        for txt, cmd, color in [
            ("↺",  self._refresh,   C["summary"]),
            ("⬇",  self._export_txt, C["storage"]),
            ("📷", self._snapshot,   C["gpu"]),
        ]:
            b = ctk.CTkButton(
                btns, text=txt, font=("Segoe UI", 13),
                fg_color=CARD_HL, hover_color=BORDER,
                text_color=color, width=10, height=32, corner_radius=6,
                command=cmd,
            )
            b.pack(side="left", expand=True, fill="x", padx=2)

        # ── Content pane ──────────────────────────────────────────────────────
        self.content_outer = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.content_outer.pack(side="left", fill="both", expand=True)

        # Section header bar
        hbar = ctk.CTkFrame(self.content_outer, fg_color=BG, height=64)
        hbar.pack(fill="x", padx=24, pady=(20, 0))
        hbar.pack_propagate(False)

        title_col = ctk.CTkFrame(hbar, fg_color="transparent")
        title_col.pack(side="left", anchor="w", fill="y")
        self.section_title = ctk.CTkLabel(
            title_col, text="", font=F_TITLE, text_color=TEXT_PRI, anchor="w")
        self.section_title.pack(anchor="w", pady=(6, 0))
        self.section_subtitle = ctk.CTkLabel(
            title_col, text="", font=F_SMALL, text_color=TEXT_DIM, anchor="w")
        self.section_subtitle.pack(anchor="w", pady=(2, 0))

        # Thin divider under header
        ctk.CTkFrame(self.content_outer, height=1, fg_color=BORDER).pack(
            fill="x", padx=24, pady=(8, 0))

        # Scrollable content
        self.scroll = ctk.CTkScrollableFrame(
            self.content_outer, fg_color=BG,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=CARD_HL,
        )
        self.scroll.pack(fill="both", expand=True, padx=18, pady=(10, 16))

    def _show_loading(self):
        self.loading_lbl = ctk.CTkLabel(
            self.scroll,
            text="Collecting system information…",
            font=("Segoe UI", 13), text_color=TEXT_SEC,
        )
        self.loading_lbl.pack(expand=True, pady=80)

    def _load_data(self):
        self.data = si.collect_all()
        self.root.after(0, self._on_data_ready)

    def _on_data_ready(self):
        try:
            self.loading_lbl.destroy()
        except Exception:
            pass
        self._show_section("summary")
        if not self._live_thread_started():
            threading.Thread(target=self._live_loop, daemon=True).start()
            self._live_started = True

    def _live_thread_started(self):
        return getattr(self, "_live_started", False)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _card(self, parent, color=None, pady=(0, 12)):
        outer = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=10)
        outer.pack(fill="x", pady=pady, padx=2)
        return outer

    def _section_header(self, parent, text, color, padx=18, pady=(14, 8)):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", fill="x", padx=padx, pady=pady)
        bar = ctk.CTkFrame(row, width=3, height=14, fg_color=color, corner_radius=2)
        bar.pack(side="left", padx=(0, 10))
        bar.pack_propagate(False)
        ctk.CTkLabel(row, text=text, font=F_HEAD,
                     text_color=color, anchor="w").pack(side="left")

    def _row(self, parent, label, value, padx=18, pady=(3, 3)):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=padx, pady=pady)
        ctk.CTkLabel(row, text=label, font=F_BODY, text_color=TEXT_SEC,
                     width=160, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=str(value), font=F_BODY, text_color=TEXT_PRI,
                     anchor="w", wraplength=480, justify="left").pack(
            side="left", fill="x", expand=True)

    def _pbar(self, parent, left_text, pct, right_text="",
              color=ACCENT_PRI, padx=18, pady=(6, 10)):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=padx, pady=pady)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=left_text, font=F_BODY,
                     text_color=TEXT_SEC, anchor="w").pack(side="left")
        rlbl = ctk.CTkLabel(top, text=right_text, font=F_SMALL,
                             text_color=TEXT_DIM, anchor="e")
        rlbl.pack(side="right")

        bar = ctk.CTkProgressBar(frame, height=8, corner_radius=4,
                                  fg_color=BORDER, progress_color=color)
        bar.pack(fill="x", pady=(4, 0))
        bar.set(min(pct / 100.0, 1.0))
        return bar, rlbl

    def _spacer(self, parent, h=10):
        ctk.CTkLabel(parent, text="", height=h).pack()

    def _show_status(self, msg: str, color: str = None):
        self.status_lbl.configure(text=msg, text_color=color or C["storage"])
        self.root.after(4000, lambda: self.status_lbl.configure(text=""))

    # ── Navigation ────────────────────────────────────────────────────────────

    def _show_section(self, key):
        for k, parts in self.nav_btns.items():
            sel = (k == key)
            parts["indicator"].configure(
                fg_color=C.get(k, ACCENT_PRI) if sel else "transparent")
            parts["btn"].configure(
                fg_color=CARD_HL if sel else "transparent",
                text_color=C.get(k, TEXT_PRI) if sel else TEXT_SEC,
            )

        icon = next((i for k, i, _ in SECTIONS if k == key), "")
        label = next((l for k, _, l in SECTIONS if k == key), key)
        self.section_title.configure(text=f"{icon}   {label}",
                                      text_color=C.get(key, TEXT_PRI))

        sub_map = {
            "summary":     "Quick overview of all hardware",
            "os":          "Operating system details and uptime",
            "cpu":         "Processor specs with live per-core usage",
            "ram":         "Installed memory modules and usage",
            "motherboard": "Mainboard, chipset, and BIOS",
            "gpu":         "Graphics adapters and display info",
            "storage":     "Disk drives and partition usage",
            "network":     "Active network adapters",
            "audio":       "Audio devices",
        }
        self.section_subtitle.configure(text=sub_map.get(key, ""))

        for w in self.scroll.winfo_children():
            w.destroy()
        self.live_widgets.clear()

        self.current_section = key
        {
            "summary":     self._build_summary,
            "os":          self._build_os,
            "cpu":         self._build_cpu,
            "ram":         self._build_ram,
            "motherboard": self._build_motherboard,
            "gpu":         self._build_gpu,
            "storage":     self._build_storage,
            "network":     self._build_network,
            "audio":       self._build_audio,
        }.get(key, lambda: None)()

    def _refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.live_widgets.clear()
        self._show_loading()
        threading.Thread(target=self._load_data, daemon=True).start()
        self._show_status("Refreshing…", TEXT_SEC)

    # ── Export TXT ────────────────────────────────────────────────────────────

    def _export_txt(self):
        if not self.data:
            self._show_status("No data yet", TEXT_DIM)
            return
        default = f"duccky-specs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(
            title="Export specs as text",
            defaultextension=".txt",
            initialfile=default,
            filetypes=[("Text File", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            text = self._format_text_report()
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self._show_status(f"Exported: {os.path.basename(path)}", C["storage"])
        except Exception as e:
            self._show_status(f"Export failed: {e}", "#ff6b6b")

    def _format_text_report(self) -> str:
        d = self.data
        lines = []
        bar = "=" * 80

        lines.append(bar)
        lines.append("                    DUCCKY — SYSTEM INFORMATION REPORT")
        lines.append(f"                    Generated: {datetime.now():%Y-%m-%d  %H:%M:%S}")
        lines.append(bar)
        lines.append("")

        def section(title):
            lines.append(title)
            lines.append("-" * 80)

        def kv(label, value):
            if value not in (None, "", 0, "0"):
                lines.append(f"  {label:<22}{value}")

        # OS
        section("OPERATING SYSTEM")
        o = d.get("os", {})
        kv("Caption",       o.get("caption"))
        kv("Version",       o.get("version"))
        kv("Build",         o.get("build"))
        kv("Architecture",  o.get("architecture"))
        kv("Hostname",      o.get("hostname"))
        kv("Uptime",        o.get("uptime"))
        kv("Install Date",  o.get("install_date"))
        lines.append("")

        # CPU
        section("CPU")
        cpu = d.get("cpu", {})
        kv("Name",            cpu.get("name"))
        kv("Manufacturer",    cpu.get("manufacturer"))
        kv("Socket",          cpu.get("socket"))
        mhz = cpu.get("freq_max_mhz", 0)
        if mhz:
            kv("Max Speed", f"{mhz/1000:.2f} GHz" if mhz > 1000 else f"{mhz:.0f} MHz")
        kv("Physical Cores",  cpu.get("cores_physical"))
        kv("Logical Cores",   cpu.get("cores_logical"))
        if cpu.get("l2_cache_kb"): kv("L2 Cache", f"{cpu['l2_cache_kb']} KB")
        if cpu.get("l3_cache_kb"): kv("L3 Cache", f"{cpu['l3_cache_kb']} KB")
        lines.append("")

        # RAM
        section("MEMORY")
        ram = d.get("ram", {})
        kv("Total",         si.bytes_to_human(ram.get("total", 0)))
        kv("Used",          f"{si.bytes_to_human(ram.get('used',0))}  ({ram.get('percent',0):.0f}%)")
        kv("Available",     si.bytes_to_human(ram.get("available", 0)))
        kv("Type",          ram.get("memory_type"))
        if ram.get("speed_mhz"): kv("Speed", f"{ram['speed_mhz']} MHz")
        kv("Configuration", ram.get("channels"))
        kv("Slots Used",    len(ram.get("modules", [])))
        for i, m in enumerate(ram.get("modules", [])):
            lines.append(f"  Module {i+1}  ({m.get('slot','')})")
            lines.append(f"    Capacity:           {si.bytes_to_human(m.get('capacity', 0))}")
            if m.get("type_str"):     lines.append(f"    Type:               {m['type_str']}")
            if m.get("speed"):        lines.append(f"    Speed:              {m['speed']} MHz")
            if m.get("manufacturer"): lines.append(f"    Manufacturer:       {m['manufacturer']}")
            if m.get("part_number"):  lines.append(f"    Part Number:        {m['part_number']}")
        lines.append("")

        # Motherboard
        section("MOTHERBOARD")
        mb = d.get("motherboard", {})
        kv("Manufacturer", mb.get("manufacturer"))
        kv("Model",        mb.get("product"))
        kv("Version",      mb.get("version"))
        kv("BIOS Vendor",  mb.get("bios_vendor"))
        kv("BIOS Version", mb.get("bios_version"))
        kv("BIOS Date",    mb.get("bios_date"))
        lines.append("")

        # GPU
        section("GRAPHICS")
        for i, g in enumerate(d.get("gpu", [])):
            if i: lines.append("")
            kv("Name",            g.get("name"))
            kv("VRAM",            g.get("vram"))
            kv("Driver Version",  g.get("driver_version"))
            kv("Driver Date",     g.get("driver_date"))
        lines.append("")

        # Displays
        section("DISPLAYS")
        for i, disp in enumerate(d.get("displays", []), 1):
            if i > 1: lines.append("")
            tag = "Primary" if disp.get("primary") else "Secondary"
            lines.append(f"  Display {i}  ({tag})")
            lines.append(f"    Monitor:            {disp['name']}")
            lines.append(f"    Resolution:         {disp['width']}×{disp['height']} @ {disp['refresh']} Hz")
            if disp.get("adapter_name"):
                lines.append(f"    Adapter:            {disp['adapter_name']}")
        lines.append("")

        # Storage
        section("STORAGE")
        for i, drv in enumerate(d.get("storage", [])):
            if i: lines.append("")
            mp = drv.get("mountpoint", "")
            model = drv.get("model", "")
            tp = drv.get("drive_type", "")
            header = f"  {mp}"
            if model: header += f"  —  {model}"
            if tp:    header += f"  [{tp}]"
            lines.append(header)
            lines.append(f"    File System:        {drv.get('fstype','')}")
            lines.append(f"    Total:              {si.bytes_to_human(drv.get('total', 0))}")
            lines.append(f"    Used:               {si.bytes_to_human(drv.get('used', 0))}  ({drv.get('percent',0):.0f}%)")
            lines.append(f"    Free:               {si.bytes_to_human(drv.get('free', 0))}")
        lines.append("")

        # Network
        section("NETWORK")
        for i, a in enumerate(d.get("network", [])):
            if i: lines.append("")
            lines.append(f"  {a.get('name','')}")
            if a.get("speed_mbps"): lines.append(f"    Speed:              {a['speed_mbps']} Mbps")
            if a.get("ipv4"):       lines.append(f"    IPv4:               {a['ipv4']}")
            if a.get("mac"):        lines.append(f"    MAC:                {a['mac']}")
            if a.get("mtu"):        lines.append(f"    MTU:                {a['mtu']}")
        lines.append("")

        # Audio
        section("AUDIO")
        for i, dev in enumerate(d.get("audio", [])):
            if i: lines.append("")
            lines.append(f"  {dev.get('name','')}")
            if dev.get("manufacturer"): lines.append(f"    Manufacturer:       {dev['manufacturer']}")
            if dev.get("status"):       lines.append(f"    Status:             {dev['status']}")
        lines.append("")

        lines.append(bar)
        lines.append("                  Generated by Duccky System Information")
        lines.append(bar)
        return "\n".join(lines)

    # ── Snapshot PNG ──────────────────────────────────────────────────────────

    def _snapshot(self):
        if not self.data:
            self._show_status("No data yet", TEXT_DIM)
            return
        default = f"duccky-snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        path = filedialog.asksaveasfilename(
            title="Save spec snapshot",
            defaultextension=".png",
            initialfile=default,
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            spec_image.render(self.data, path)
            self._show_status(f"Saved: {os.path.basename(path)}", C["gpu"])
        except Exception as e:
            self._show_status(f"Snapshot failed: {e}", "#ff6b6b")

    # ── Summary ───────────────────────────────────────────────────────────────

    def _build_summary(self):
        p = self.scroll
        d = self.data

        # OS
        card = self._card(p)
        self._section_header(card, "Operating System", C["os"])
        self._row(card, "OS", d["os"].get("caption", ""))
        build = d["os"].get("build", "")
        ver = d["os"].get("version", "")
        self._row(card, "Version", f"{ver}  (Build {build})" if build else ver)
        self._row(card, "Uptime", d["os"].get("uptime", ""))
        self._spacer(card)

        # CPU
        card = self._card(p)
        self._section_header(card, "CPU", C["cpu"])
        cpu = d["cpu"]
        mhz = cpu.get("freq_max_mhz", 0)
        freq_str = (f"{mhz/1000:.2f} GHz" if mhz > 1000 else
                    f"{mhz:.0f} MHz" if mhz else "")
        name_row = ctk.CTkFrame(card, fg_color="transparent")
        name_row.pack(fill="x", padx=18, pady=(2, 0))
        ctk.CTkLabel(name_row, text=cpu.get("name", ""), font=F_BODY,
                     text_color=TEXT_PRI, anchor="w").pack(side="left")
        if freq_str:
            ctk.CTkLabel(name_row, text=freq_str, font=F_SMALL,
                         text_color=TEXT_DIM).pack(side="right")
        self._row(card, "Cores / Threads",
                  f"{cpu.get('cores_physical','?')} cores  /  "
                  f"{cpu.get('cores_logical','?')} logical")
        bar, rlbl = self._pbar(card, "CPU Usage", 0, "0%", color=C["cpu"])
        self.live_widgets["sum_cpu"] = (bar, rlbl)
        self._spacer(card)

        # RAM
        card = self._card(p)
        self._section_header(card, "RAM", C["ram"])
        ram = d["ram"]
        parts = [si.bytes_to_human(ram["total"])]
        if ram.get("channels"):    parts.append(ram["channels"])
        if ram.get("memory_type"): parts.append(ram["memory_type"])
        if ram.get("speed_mhz"):   parts.append(f"@ {ram['speed_mhz']} MHz")
        self._row(card, "Memory", "  ".join(parts))
        ram_rlbl = ctk.CTkLabel(card, text="", font=F_SMALL, text_color=TEXT_DIM)
        ram_rlbl.pack(anchor="e", padx=18, pady=(0, 2))
        bar2, rlbl2 = self._pbar(card, "RAM Usage", ram["percent"],
                                  f"{ram['percent']:.0f}%", color=C["ram"])
        self.live_widgets["sum_ram"] = (bar2, rlbl2, ram_rlbl)
        self._spacer(card)

        # Motherboard
        mb = d["motherboard"]
        mb_name = f"{mb.get('manufacturer','')} {mb.get('product','')}".strip()
        if mb_name:
            card = self._card(p)
            self._section_header(card, "Motherboard", C["motherboard"])
            self._row(card, "Board", mb_name)
            if mb.get("bios_version"):
                self._row(card, "BIOS",
                          f"{mb.get('bios_vendor','')} {mb.get('bios_version','')}".strip())
            self._spacer(card)

        # GPU
        if d["gpu"]:
            card = self._card(p)
            self._section_header(card, "Graphics", C["gpu"])
            for g in d["gpu"]:
                if g.get("is_virtual"):
                    continue
                self._row(card, "GPU", g["name"])
                if g.get("vram") and g["vram"] != "N/A":
                    self._row(card, "VRAM", g["vram"])
            for disp in d.get("displays", []):
                tag = "Display" + ("  (Primary)" if disp.get("primary") else "")
                val = f"{disp['name']}  —  {disp['width']}×{disp['height']} @ {disp['refresh']} Hz"
                self._row(card, tag, val)
            self._spacer(card)

        # Storage
        if d["storage"]:
            card = self._card(p)
            self._section_header(card, "Storage", C["storage"])
            for drv in d["storage"]:
                lbl = drv["mountpoint"]
                if drv.get("model"):       lbl += f"  {drv['model']}"
                if drv.get("drive_type"):  lbl += f"  [{drv['drive_type']}]"
                pct = drv["percent"]
                color = ("#ff6b6b" if pct > 85 else
                         "#ffa94d" if pct > 65 else C["storage"])
                self._pbar(card, lbl, pct,
                           f"{si.bytes_to_human(drv['used'])} / "
                           f"{si.bytes_to_human(drv['total'])}", color=color)
            self._spacer(card)

    # ── OS ────────────────────────────────────────────────────────────────────

    def _build_os(self):
        d = self.data["os"]
        card = self._card(self.scroll)
        self._section_header(card, "Operating System", C["os"])
        for lbl, val in [
            ("Name",          d.get("caption", "")),
            ("Version",       d.get("version", "")),
            ("Build",         d.get("build", "")),
            ("Architecture",  d.get("architecture", "")),
            ("Hostname",      d.get("hostname", "")),
            ("Uptime",        d.get("uptime", "")),
            ("Install Date",  d.get("install_date", "")),
        ]:
            if val:
                self._row(card, lbl, val)
        self._spacer(card)

    # ── CPU ───────────────────────────────────────────────────────────────────

    def _build_cpu(self):
        d = self.data["cpu"]
        p = self.scroll

        card = self._card(p)
        self._section_header(card, "Processor", C["cpu"])
        mhz = d.get("freq_max_mhz", 0)
        freq_str = (f"{mhz/1000:.2f} GHz" if mhz > 1000 else
                    f"{mhz:.0f} MHz" if mhz else "N/A")
        for lbl, val in [
            ("Name",           d.get("name", "")),
            ("Manufacturer",   d.get("manufacturer", "")),
            ("Socket",         d.get("socket", "")),
            ("Max Speed",      freq_str),
            ("Physical Cores", str(d.get("cores_physical", "?"))),
            ("Logical Cores",  str(d.get("cores_logical", "?"))),
            ("L2 Cache",       f"{d['l2_cache_kb']} KB" if d.get("l2_cache_kb") else ""),
            ("L3 Cache",       f"{d['l3_cache_kb']} KB" if d.get("l3_cache_kb") else ""),
        ]:
            if val:
                self._row(card, lbl, val)
        self._spacer(card)

        # Live usage
        card2 = self._card(p)
        self._section_header(card2, "Live Usage", C["cpu"])
        bar, rlbl = self._pbar(card2, "Overall", 0, "0%", color=C["cpu"])
        self.live_widgets["cpu_overall"] = (bar, rlbl)

        n = d.get("cores_logical", 4)
        cols = 4 if n <= 8 else 6
        grid = ctk.CTkFrame(card2, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=(6, 12))
        core_widgets = []
        for i in range(n):
            col = i % cols
            row_idx = i // cols
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=row_idx, column=col, padx=(0, 12), pady=4, sticky="ew")
            grid.columnconfigure(col, weight=1)
            ctk.CTkLabel(cell, text=f"Core {i}", font=F_SMALL,
                         text_color=TEXT_DIM, anchor="w").pack(fill="x")
            b = ctk.CTkProgressBar(cell, height=5, corner_radius=2,
                                    fg_color=BORDER, progress_color=C["cpu"])
            b.pack(fill="x", pady=(2, 0))
            b.set(0)
            l = ctk.CTkLabel(cell, text="0%", font=("Segoe UI", 8),
                              text_color=TEXT_DIM, anchor="e")
            l.pack(fill="x")
            core_widgets.append((b, l))
        self.live_widgets["cpu_cores"] = core_widgets

        # Temperature
        card3 = self._card(p)
        self._section_header(card3, "Temperature", C["cpu"])
        t_row = ctk.CTkFrame(card3, fg_color="transparent")
        t_row.pack(fill="x", padx=18, pady=(6, 14))
        t_lbl = ctk.CTkLabel(t_row, text="— °C", font=F_BIG,
                              text_color=TEXT_SEC, anchor="w")
        t_lbl.pack(side="left")
        ctk.CTkLabel(
            t_row,
            text="Hardware monitoring may not be available on all\nsystems — install LibreHardwareMonitor for support.",
            font=F_SMALL, text_color=TEXT_DIM, justify="left",
        ).pack(side="left", padx=(16, 0))
        self.live_widgets["cpu_temp"] = t_lbl

    # ── RAM ───────────────────────────────────────────────────────────────────

    def _build_ram(self):
        d = self.data["ram"]
        p = self.scroll

        card = self._card(p)
        self._section_header(card, "Memory Usage", C["ram"])
        used = si.bytes_to_human(d["used"])
        total = si.bytes_to_human(d["total"])
        avail = si.bytes_to_human(d["available"])
        s_row = ctk.CTkFrame(card, fg_color="transparent")
        s_row.pack(fill="x", padx=18, pady=(6, 4))
        ctk.CTkLabel(s_row, text=used, font=F_BIG, text_color=TEXT_PRI).pack(side="left")
        ctk.CTkLabel(s_row, text=f"  /  {total}", font=("Segoe UI", 13),
                     text_color=TEXT_SEC).pack(side="left", pady=4)
        bar, rlbl = self._pbar(card, f"In use", d["percent"],
                                f"{d['percent']:.0f}%   ·   {avail} free",
                                color=C["ram"])
        self.live_widgets["ram_bar"] = (bar, rlbl)
        self._spacer(card)

        card2 = self._card(p)
        self._section_header(card2, "Specification", C["ram"])
        for lbl, val in [
            ("Total",         si.bytes_to_human(d["total"])),
            ("Type",          d.get("memory_type", "") or "Unknown"),
            ("Speed",         f"{d['speed_mhz']} MHz" if d.get("speed_mhz") else ""),
            ("Configuration", d.get("channels", "")),
            ("Slots Used",    str(len(d.get("modules", [])))),
        ]:
            if val:
                self._row(card2, lbl, val)
        self._spacer(card2)

        if d.get("modules"):
            card3 = self._card(p)
            self._section_header(card3, "Memory Modules", C["ram"])
            for mod in d["modules"]:
                mf = ctk.CTkFrame(card3, fg_color=CARD_HL, corner_radius=8)
                mf.pack(fill="x", padx=14, pady=(0, 10))
                hdr = ctk.CTkFrame(mf, fg_color="transparent")
                hdr.pack(fill="x", padx=14, pady=(10, 4))
                ctk.CTkLabel(hdr, text=mod.get("slot", "Slot"),
                             font=F_HEAD, text_color=C["ram"]).pack(side="left")
                ctk.CTkLabel(hdr, text=si.bytes_to_human(mod.get("capacity", 0)),
                             font=F_BODY, text_color=TEXT_PRI).pack(side="right")
                for lbl, val in [
                    ("Type",         mod.get("type_str", "")),
                    ("Speed",        f"{mod.get('speed','')} MHz" if mod.get("speed") else ""),
                    ("Manufacturer", mod.get("manufacturer", "")),
                    ("Part Number",  mod.get("part_number", "")),
                ]:
                    if val:
                        self._row(mf, lbl, val, padx=14)
                self._spacer(mf, 8)
            self._spacer(card3, 4)

    # ── Motherboard ───────────────────────────────────────────────────────────

    def _build_motherboard(self):
        d = self.data["motherboard"]
        p = self.scroll
        SKIP = {"to be filled by o.e.m.", ""}

        card = self._card(p)
        self._section_header(card, "Motherboard", C["motherboard"])
        for lbl, val in [
            ("Manufacturer", d.get("manufacturer", "")),
            ("Model",        d.get("product", "")),
            ("Version",      d.get("version", "")),
        ]:
            if val and val.lower() not in SKIP:
                self._row(card, lbl, val)
        self._spacer(card)

        card2 = self._card(p)
        self._section_header(card2, "BIOS", C["motherboard"])
        for lbl, val in [
            ("Vendor",  d.get("bios_vendor", "")),
            ("Version", d.get("bios_version", "")),
            ("Date",    d.get("bios_date", "")),
        ]:
            if val:
                self._row(card2, lbl, val)
        self._spacer(card2)

    # ── GPU ───────────────────────────────────────────────────────────────────

    def _build_gpu(self):
        gpus = self.data["gpu"]
        p = self.scroll
        if not gpus:
            card = self._card(p)
            ctk.CTkLabel(card, text="No GPU information available",
                         font=F_BODY, text_color=TEXT_DIM).pack(padx=18, pady=18)
            return
        for g in gpus:
            card = self._card(p)
            self._section_header(card, g.get("name", "Graphics Adapter"), C["gpu"])
            for lbl, val in [
                ("VRAM",           g.get("vram", "")),
                ("Driver Version", g.get("driver_version", "")),
                ("Driver Date",    g.get("driver_date", "")),
            ]:
                if val and val != "N/A":
                    self._row(card, lbl, val)
            self._spacer(card)

        displays = self.data.get("displays", [])
        if displays:
            card = self._card(p)
            self._section_header(card, "Displays", C["gpu"])
            for i, disp in enumerate(displays, 1):
                tag = f"Display {i}" + ("  (Primary)" if disp.get("primary") else "")
                self._row(card, tag, disp["name"])
                self._row(card, "  Resolution",
                          f"{disp['width']}×{disp['height']} @ {disp['refresh']} Hz")
                if disp.get("adapter_name"):
                    self._row(card, "  Adapter", disp["adapter_name"])
            self._spacer(card)

    # ── Storage ───────────────────────────────────────────────────────────────

    def _build_storage(self):
        drives = self.data["storage"]
        p = self.scroll
        if not drives:
            card = self._card(p)
            ctk.CTkLabel(card, text="No storage drives found",
                         font=F_BODY, text_color=TEXT_DIM).pack(padx=18, pady=18)
            return
        for drv in drives:
            card = self._card(p)
            header = drv["mountpoint"]
            if drv.get("model"):       header += f"  —  {drv['model']}"
            if drv.get("drive_type"):  header += f"  [{drv['drive_type']}]"
            self._section_header(card, header, C["storage"])
            pct = drv["percent"]
            color = ("#ff6b6b" if pct > 85 else
                     "#ffa94d" if pct > 65 else C["storage"])
            self._pbar(card, f"Used  {pct:.0f}%", pct,
                       f"{si.bytes_to_human(drv['used'])} of "
                       f"{si.bytes_to_human(drv['total'])}", color=color)
            for lbl, val in [
                ("File System", drv.get("fstype", "")),
                ("Total Size",  si.bytes_to_human(drv["total"])),
                ("Used",        si.bytes_to_human(drv["used"])),
                ("Free",        si.bytes_to_human(drv["free"])),
                ("Device",      drv.get("device", "")),
            ]:
                if val:
                    self._row(card, lbl, val)
            self._spacer(card)

    # ── Network ───────────────────────────────────────────────────────────────

    def _build_network(self):
        adapters = self.data["network"]
        p = self.scroll
        if not adapters:
            card = self._card(p)
            ctk.CTkLabel(card, text="No active network adapters",
                         font=F_BODY, text_color=TEXT_DIM).pack(padx=18, pady=18)
            return
        for adp in adapters:
            card = self._card(p)
            self._section_header(card, adp.get("name", "Adapter"), C["network"])
            spd = adp.get("speed_mbps", 0)
            for lbl, val in [
                ("Status", "Connected"),
                ("Speed",  f"{spd} Mbps" if spd else "Unknown"),
                ("IPv4",   adp.get("ipv4", "")),
                ("MAC",    adp.get("mac", "")),
                ("MTU",    str(adp.get("mtu", ""))),
            ]:
                if val:
                    self._row(card, lbl, val)
            self._spacer(card)

    # ── Audio ─────────────────────────────────────────────────────────────────

    def _build_audio(self):
        devices = self.data["audio"]
        p = self.scroll
        if not devices:
            card = self._card(p)
            ctk.CTkLabel(card, text="No audio devices found",
                         font=F_BODY, text_color=TEXT_DIM).pack(padx=18, pady=18)
            return
        for dev in devices:
            card = self._card(p)
            self._section_header(card, dev.get("name", "Audio Device"), C["audio"])
            for lbl, val in [
                ("Manufacturer", dev.get("manufacturer", "")),
                ("Status",       dev.get("status", "")),
            ]:
                if val:
                    self._row(card, lbl, val)
            self._spacer(card)

    # ── Live update loop ──────────────────────────────────────────────────────

    def _live_loop(self):
        while not self._stop.is_set():
            live = si.get_cpu_live()
            vm = psutil.virtual_memory()
            self.root.after(0, self._apply_live, live, vm)
            time.sleep(2)

    def _apply_live(self, live, vm):
        overall = live.get("overall", 0)
        per_core = live.get("per_core", [])
        temp = live.get("temp")
        ram_pct = vm.percent
        ram_used = si.bytes_to_human(vm.used)
        ram_avail = si.bytes_to_human(vm.available)

        try:
            self.update_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass

        def _safe_set(key, pct, label=""):
            pair = self.live_widgets.get(key)
            if pair:
                try:
                    pair[0].set(pct / 100)
                    if len(pair) > 1 and label:
                        pair[1].configure(text=label)
                except Exception:
                    pass

        _safe_set("sum_cpu", overall, f"{overall:.0f}%")
        _safe_set("sum_ram", ram_pct, f"{ram_pct:.0f}%")

        trio = self.live_widgets.get("sum_ram")
        if trio and len(trio) > 2:
            try:
                trio[2].configure(text=f"{ram_used} used  ·  {ram_avail} free")
            except Exception:
                pass

        _safe_set("cpu_overall", overall, f"{overall:.0f}%")
        _safe_set("ram_bar", ram_pct, f"{ram_pct:.0f}%   ·   {ram_avail} free")

        for i, (bar, lbl) in enumerate(self.live_widgets.get("cpu_cores", [])):
            val = per_core[i] if i < len(per_core) else 0
            try:
                bar.set(val / 100)
                lbl.configure(text=f"{val:.0f}%")
                color = ("#ff6b6b" if val > 85 else
                         "#ffa94d" if val > 60 else C["cpu"])
                bar.configure(progress_color=color)
            except Exception:
                pass

        t_lbl = self.live_widgets.get("cpu_temp")
        if t_lbl:
            try:
                if temp is not None:
                    color = ("#4db6ac" if temp < 50 else
                             "#ffb74d" if temp < 75 else "#ef5350")
                    t_lbl.configure(text=f"{temp:.1f} °C", text_color=color)
                else:
                    t_lbl.configure(text="N/A", text_color=TEXT_DIM)
            except Exception:
                pass

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self._stop.set()
        self.root.destroy()
