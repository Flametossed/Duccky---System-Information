# Duccky — System Information

A modern, dark-themed desktop app for viewing detailed system hardware and software information. Built with Python and CustomTkinter.

![Duccky Screenshot](duccky-snapshot-20260508-203608.png)

## Features

- **Summary** — at-a-glance overview of all hardware
- **Operating System** — name, version, build, architecture, uptime, install date
- **CPU** — name, socket, speed, core/thread count, cache sizes, live per-core usage bars, temperature
- **RAM** — total, type, speed, channel config, per-slot module details, live usage
- **Motherboard** — manufacturer, model, BIOS vendor/version/date
- **Graphics** — GPU name, VRAM, driver version/date, connected displays with resolution and refresh rate
- **Storage** — per-drive usage bars with model, type, filesystem, and size breakdown
- **Network** — active adapters with IPv4, MAC, speed, MTU
- **Audio** — detected audio devices

Live CPU and RAM stats refresh every 2 seconds.

## Download

Grab the latest portable build from [Releases](../../releases/latest):

| Platform | File |
|----------|------|
| Windows 10/11 | `Duccky-portable.exe` — no install needed, run directly |
| Linux (x86_64) | `Duccky-portable-x86_64.AppImage` — requires FUSE2 (`libfuse2`); `chmod +x` then run |
| Linux (x86_64) | `Duccky-portable-linux-x86_64.tar.gz` — no dependencies; extract and run `./Duccky-portable-linux/Duccky` |

## Running from source

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
python main.py
```

> **Windows only:** Full hardware detail (RAM slots, GPU driver, BIOS info) uses WMI.
> On Linux, those fields fall back to what `psutil` and `/proc` expose.

## Export

Two built-in export options in the sidebar:

- **⬇ Export TXT** — saves a full spec report as a plain-text file
- **📷 Snapshot** — renders a spec summary card as a PNG image

## Building

Builds are automated via GitHub Actions on every `v*` tag push.
See [`.github/workflows/release.yml`](.github/workflows/release.yml) for the full pipeline.

To build locally:

```bash
pip install pyinstaller
# Windows
pyinstaller --onefile --windowed --name Duccky-portable --icon logo.ico --add-data "logo.png;." --add-data "logo.ico;." main.py

# Linux
pyinstaller --onefile --name Duccky --add-data "logo.png:." --add-data "logo.ico:." main.py
```
