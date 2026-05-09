# GPS Monitor

A multi-panel GPS monitoring application with a 3D globe, sky view, satellite table,
world map, and NTP-synchronized time display. Supports real GPS hardware (NMEA, UBX,
SiRF) as well as a full simulation mode and live TLE propagation via CelesTrak.

Built entirely with [Claude Code](https://claude.ai/code) as a worked example of
AI-assisted software development.

---

## Running from source

**Install dependencies**

```bash
pip install -r requirements.txt
pip install cartopy shapely
```

**Launch**

```bash
# Simulation mode — no hardware required, all panels populate within ~2 s
python main.py --simulate

# Live TLE mode — downloads real satellite positions from CelesTrak
python main.py --tle

# Real GPS receiver
python main.py --port /dev/tty.usbserial-0001   # macOS example
python main.py --port COM3                       # Windows example
```

---

## Building a redistributable

Produces a self-contained app that requires no Python installation on the target machine.

**macOS** (run on a Mac)

```bash
pip install pyinstaller Pillow
bash build/build_mac.sh
```

Output: `dist/GPS Monitor.app` and `dist/GPS_Monitor_1.0_macOS.dmg`

**Windows** (run on a Windows machine)

```bat
pip install pyinstaller Pillow
build\build_windows.bat
```

Output: `dist\GPS Monitor\` directory and (if [Inno Setup 6](https://jrsoftware.org/isinfo.php)
is installed) `dist\GPS_Monitor_1.0_Setup.exe`

See [BUILD.md](BUILD.md) for full details, troubleshooting, and bundle size notes.

---

## Features

- **3D globe** — VisPy OpenGL rendering with real-time satellite positions, terrain
  toggle, hover tooltips, and observer marker
- **Sky view** — polar azimuth/elevation plot, North up
- **Satellite table** — sortable, colour-coded by signal strength, up to 300 satellites
- **World map** — interactive folium/Leaflet map with sub-satellite ground tracks
- **Time display** — GPS sentence time + NTP weighted-average with ±ms uncertainty
- **Constellation filter** — toggle GPS, GLONASS, Galileo, BeiDou, QZSS, NavIC,
  Starlink, OneWeb, Iridium, ISS independently

## Documentation

- [MANUAL.md](MANUAL.md) — full user manual covering every panel and feature
- [BUILD.md](BUILD.md) — build system reference
- [docs/](docs/) — per-module developer documentation
