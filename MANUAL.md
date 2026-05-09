# GPS Monitor — User Manual

GPS Monitor is a multi-panel desktop application that displays real-time satellite positions and GNSS data from hardware receivers, live CelesTrak TLE propagation, or a built-in orbital simulator. It was built entirely using **Claude Code** as a demonstration of AI-assisted software development, and the repository is intended as a worked example of that workflow.

---

## Contents

1. [About This Repository](#1-about-this-repository)
2. [Installation](#2-installation)
3. [Running the Application](#3-running-the-application)
4. [Application Window Layout](#4-application-window-layout)
5. [Data Source Toolbar](#5-data-source-toolbar)
6. [Constellation Filter Toolbar](#6-constellation-filter-toolbar)
7. [Globe (Central Panel)](#7-globe-central-panel)
8. [Satellite Table (Left Dock)](#8-satellite-table-left-dock)
9. [Sky View (Right Dock — Top)](#9-sky-view-right-dock--top)
10. [Time Display (Right Dock — Middle)](#10-time-display-right-dock--middle)
11. [Satellite Hover Panel (Right Dock — Bottom)](#11-satellite-hover-panel-right-dock--bottom)
12. [World Map (Bottom Dock)](#12-world-map-bottom-dock)
13. [Status Bar](#13-status-bar)
14. [Understanding the Data](#14-understanding-the-data)
15. [Repository Structure](#15-repository-structure)
16. [Architecture Reference](#16-architecture-reference)
17. [Built with Claude Code](#17-built-with-claude-code)

---

## 1. About This Repository

This repository demonstrates building a complete, non-trivial Python desktop application entirely through conversations with **Claude Code** — Anthropic's CLI coding assistant. Every source file, every bug fix, and every architectural decision in this project was produced through an iterative dialogue, starting from an empty directory.

The application itself is a fully functional GPS/GNSS monitoring tool. It is also a reference example showing:

- How to structure a multi-threaded PyQt6 application
- How to use VisPy for real-time 3D rendering
- How to integrate live satellite TLE data from CelesTrak
- How to write a persistent local data store as a fallback for unreliable network access
- The `moveToThread()` pattern for keeping the UI responsive under heavy computation
- Screen-space projection for accurate hover detection over 3D objects

The `logs/` directory contains the Claude Code session `.jsonl` logs from the original build sessions.

---

## 2. Installation

### Prerequisites

- Python 3.11 or later
- macOS, Windows, or Linux

### Install Dependencies

```bash
pip install -r requirements.txt
pip install cartopy shapely
```

Full package list:

| Package | Purpose |
|---------|---------|
| PyQt6 | GUI framework |
| PyQt6-WebEngine | Embedded browser for the folium world map |
| vispy | OpenGL 3D globe rendering |
| matplotlib | Sky view polar plot; globe terrain texture generation |
| folium | Interactive HTML/Leaflet world map |
| pyserial | Serial port communication with GPS hardware |
| pynmea2 | NMEA 0183 sentence parsing |
| pyubx2 | u-blox UBX binary protocol parsing |
| ntplib | NTP time queries |
| numpy | Vectorised coordinate transforms and array operations |
| sgp4 | SGP4 orbital propagation from TLE data |
| certifi | Trusted CA certificates for HTTPS downloads on macOS |
| cartopy | Globe coastlines and terrain texture (Natural Earth shapefiles) |
| shapely | Geometry library required by cartopy |

> **macOS note**: Python on macOS does not trust the system certificate store for HTTPS. `main.py` patches `ssl._create_default_https_context` at startup to use certifi's bundle. This happens before any import that may trigger a network request, so it must stay at the top of `main.py`.

---

## 3. Running the Application

```bash
# Simulation mode — no hardware or internet required
# All panels populate within ~2 seconds
python main.py --simulate

# Live TLE mode — downloads real satellite data from CelesTrak on startup
# Requires an internet connection; first launch takes ~30 seconds to download
python main.py --tle

# Hardware GPS receiver on a specific serial port
python main.py --port /dev/ttyUSB0      # Linux / macOS
python main.py --port COM3              # Windows

# No arguments — attempts serial auto-detection, falls back to simulation
python main.py
```

You can also switch data sources at any time from within the application using the toolbar — no restart required.

---

## 4. Application Window Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  GPS Source: [Simulation ▼]  [⟳ Refresh]  [Connect]  ● Connected  │  ← Source toolbar
│  Systems: [GPS][GLONASS][Galileo][BeiDou][QZSS]…   12  8  9  0…    │  ← Constellation toolbar
├──────────────────┬──────────────────────────────┬───────────────────┤
│                  │                              │   Sky View        │
│  Satellite       │                              │                   │
│  Table           │        3D Globe              ├───────────────────┤
│                  │      (central widget)        │   Time Display    │
│  PRN  Sys  El…   │                              ├───────────────────┤
│                  │                              │   Hover Panel     │
│                  │                              │                   │
├──────────────────┴──────────────────────────────┴───────────────────┤
│                        World Map                                     │
└─────────────────────────────────────────────────────────────────────┘
                                           Status bar ────────────────┘
```

All panels are dockable and resizable. The three right-side panels are stacked in a vertical splitter — drag the splitter handles to adjust their relative heights.

---

## 5. Data Source Toolbar

The top toolbar selects and controls the GPS data source.

### Source Dropdown

| Option | Description |
|--------|-------------|
| Simulation | Keplerian orbital mechanics, no hardware or internet required |
| Live TLE (CelesTrak) | Real satellite positions via SGP4 propagation using downloaded TLE data |
| Serial ports | Any discovered COM/tty port is listed here |

### Buttons

- **⟳ Refresh** — Rescans for attached serial ports and updates the dropdown.
- **Connect** — Applies the currently selected source. Stops the existing data stream and starts the new one. Safe to click at any time.

### Status Indicator

A coloured LED dot shows the connection state:

| Colour | Meaning |
|--------|---------|
| Grey | Not connected |
| Yellow | Connecting / downloading TLE data |
| Green | Receiving data |
| Red | Error |

The protocol badge (far right of toolbar) shows the active protocol: `SIM`, `TLE`, `NMEA`, `UBX`, `SiRF`, or a combined string like `TLE+GPS+GAL+BDS`.

### Terrain Toggle

The **Terrain** button (top-right of toolbar) overlays a satellite imagery texture on the globe. Requires `cartopy` and `shapely`. The texture is generated on first use (takes a few seconds) and cached for the rest of the session.

---

## 6. Constellation Filter Toolbar

The second toolbar controls which satellite systems are displayed.

Each button represents one constellation. When checked (coloured), satellites from that system are shown. When unchecked (dark outline), they are hidden.

| Button | System | Typical Satellite Count |
|--------|--------|------------------------|
| GPS | US GPS | ~31 |
| GLONASS | Russian GLONASS | ~24 |
| Galileo | European Galileo | ~27 |
| BeiDou | Chinese BeiDou | ~35+ |
| QZSS | Japanese QZSS | 4 |
| NavIC | Indian NavIC | 7 (simulation only) |
| Starlink | SpaceX Starlink | 100–2000 |
| OneWeb | OneWeb LEO | ~651 |
| Iridium | Iridium NEXT | ~66 |
| ISS/Sta | ISS and space stations | varies |

**All** and **None** buttons select or deselect everything at once.

The number to the right of each button shows the count of currently visible (above-horizon) satellites for that system. This updates live every second.

> Constellation changes take effect immediately and are forwarded to the active data source — the simulator or TLE propagator only computes satellites for enabled systems, saving CPU.

---

## 7. Globe (Central Panel)

The centrepiece of the application. An interactive 3D globe rendered with VisPy (OpenGL).

### What Is Displayed

| Visual Element | Description |
|----------------|-------------|
| Blue sphere | Earth's oceans (semi-transparent) |
| Green lines | Coastlines from Natural Earth 110m dataset |
| Blue grid | Graticule — latitude/longitude lines every 30° |
| Bright blue ring | Equator |
| Coloured dots | Satellites, coloured by constellation |
| Yellow star | Observer position (your location) |
| Terrain texture | Optional — satellite imagery overlay (Terrain button) |

Dots are rendered at three visual radii depending on orbital altitude:
- **LEO** (< 2,000 km): close to the surface — Starlink, OneWeb, Iridium, ISS
- **MEO** (2,000–30,000 km): mid-distance — GPS, GLONASS, Galileo, BeiDou
- **GEO/HEO** (> 30,000 km): far from the surface — geostationary satellites

### Mouse Controls

| Action | Effect |
|--------|--------|
| Left-click drag | Rotate the globe |
| Scroll wheel | Zoom in/out |
| Right-click drag **on the observer star** | Move the observer position |
| Hover over a satellite dot | Show satellite details in the Hover Panel |
| Double-click near a satellite | Open a floating detail dialog |

> **Tip**: To move the observer, right-click within about 24 pixels of the yellow star, then drag to the new location. Release to confirm — the World Map and all elevation/azimuth computations update immediately.

### Satellite Dot Colours

Each constellation has a fixed colour (matching the toolbar buttons). Within that colour, dot opacity indicates signal strength:

| Opacity | Meaning |
|---------|---------|
| Fully opaque | SNR ≥ 25 dBHz, above horizon |
| Semi-transparent | SNR < 25 dBHz, above horizon |
| Very dim | Below horizon (back side of globe) |

### Back-Hemisphere Satellites

Satellites on the back half of the globe are visible because they are rendered without depth testing — they always paint over the Earth surface, regardless of which side they are on. This is intentional: all satellites are real and worth knowing about, not just those directly overhead.

---

## 8. Satellite Table (Left Dock)

A sortable table showing all tracked satellites.

### Columns

| Column | Description |
|--------|-------------|
| PRN | Satellite identifier number |
| System | Constellation (GPS, GLONASS, etc.) |
| El° | Elevation above the horizon, degrees |
| Az° | Azimuth (compass bearing), degrees |
| SNR (dBHz) | Signal-to-noise ratio |
| Used | Whether this satellite contributed to the position fix |

Click any column header to sort. Click again to reverse sort.

### Row Colours

Rows are coloured using the constellation's system colour at varying intensities:

| Condition | Appearance |
|-----------|-----------|
| SNR ≥ 35 dBHz | Bright text, moderate coloured background |
| SNR 25–35 dBHz | Medium text, dim background |
| SNR < 25 dBHz, above horizon | Muted text, very dim background |
| Below horizon or no signal | Dark, faded text and background |

The table is capped at 300 rows (the 300 satellites with the highest elevation) to keep scrolling responsive. The globe always shows the full dataset.

---

## 9. Sky View (Right Dock — Top)

A polar plot showing satellite positions as seen from the observer.

- **Centre** = zenith (directly overhead)
- **Edge** = horizon (0° elevation)
- **North** is up; directions go clockwise (compass convention)
- Concentric rings mark 60° and 30° elevation

Each dot is coloured by constellation and sized proportionally to SNR (`size = max(40, snr × 2.5)`). The satellite PRN number is annotated next to each dot.

The sky view refreshes at most once per second (throttled to avoid overloading matplotlib's redraw path).

---

## 10. Time Display (Right Dock — Middle)

Shows multiple simultaneous time sources for comparison.

| Row | Source | Notes |
|-----|--------|-------|
| System UTC | Your computer's clock | Updates every 100 ms |
| GPS Time | Last UTC time from the GPS data stream | `HH:MM:SS` |
| GPS Date | Last date from the GPS data stream | `DD/MM/YYYY` |
| NTP Time | Weighted average from 8 NTP servers | Updates every ~30 s |
| NTP Uncertainty | 1σ uncertainty of the NTP estimate | Typically < 5 ms on a good connection |
| NTP Servers | Number of servers included after outlier rejection | Out of 8 queried |
| GPS-NTP Offset | Difference between GPS time and NTP | `+/−` ms |

### NTP Methodology

Eight servers are queried in parallel (`pool.ntp.org`, Google, Cloudflare, Ubuntu, Windows). Responses with round-trip delays ≥ 10 s are discarded. Outliers beyond 2 standard deviations from the median are removed. The remaining results are combined using inverse-delay-squared weighting to produce a single offset and uncertainty estimate.

---

## 11. Satellite Hover Panel (Right Dock — Bottom)

Shows detailed information for the satellite currently under the cursor on the globe.

When the cursor moves within 12 pixels of a satellite dot, the panel displays:

| Field | Description |
|-------|-------------|
| Name | Full TLE name (e.g. "GPS BIIR-2 (PRN 13)") or "SYSTEM PRN n" |
| System | Constellation, coloured in its system colour |
| PRN | Satellite identifier |
| Elevation | Degrees above horizon; green > 10°, yellow > 0°, grey ≤ 0° |
| Azimuth | Compass bearing from observer |
| SNR | Signal strength in dBHz; green ≥ 35, yellow ≥ 25, orange > 0 |
| In fix | Whether this satellite contributes to the position fix |
| Sub-sat | Geographic latitude and longitude directly below the satellite |
| Altitude | Height above Earth's surface in km |

Moving the cursor away clears the panel back to the "hover over a satellite" placeholder.

> **Hardware receivers**: `name`, `Sub-sat`, and `Altitude` will show `—` because NMEA/UBX/SiRF protocols do not provide orbital position data.

---

## 12. World Map (Bottom Dock)

A 2D interactive map showing the observer's position.

- **Green circle marker** — current observer location
- **Click anywhere on the map** — moves the observer to that position (same effect as right-click dragging the star on the globe)
- The map refreshes at most every 2 seconds

When the **Terrain** toggle is on, the map switches from the dark CartoDB basemap to ESRI World Imagery satellite tiles.

The map requires `PyQt6-WebEngine` and `folium`. If either is missing at startup, a static matplotlib equirectangular fallback is used instead (click-to-move still works).

---

## 13. Status Bar

The thin bar at the bottom of the window shows:

```
Protocol: TLE+GPS+GAL+BDS | Fix: 1 | Sats: 22 used, 89 visible | Lat: 51.50740° Lon: -0.12780° Alt: 10.0m
```

| Field | Description |
|-------|-------------|
| Protocol | Active data protocol |
| Fix | Fix quality: 0 = no fix, 1 = GPS fix, 2 = DGPS, 4 = RTK |
| Sats used | Satellites contributing to the position fix |
| Sats visible | Total satellites above the horizon |
| Lat / Lon / Alt | Current observer position |

---

## 14. Understanding the Data

### Elevation and Azimuth

These are **observer-relative** angles — they depend entirely on where the observer is placed.

- **Elevation**: angle above the horizon. 0° = on the horizon, 90° = directly overhead. Negative = below the horizon (satellite on the other side of the Earth).
- **Azimuth**: compass bearing. 0°/360° = North, 90° = East, 180° = South, 270° = West.

### SNR (Signal-to-Noise Ratio)

Measured in dBHz (decibel-hertz). Higher is better.

| Range | Signal Quality |
|-------|---------------|
| ≥ 35 dBHz | Strong — used reliably in fix |
| 25–35 dBHz | Good |
| 15–25 dBHz | Weak — may be used |
| 0 dBHz | Not tracking |

### Used in Fix

A satellite is marked as "used" when:
- Elevation > 10°
- SNR > 20 dBHz
- System is one of: GPS, GLONASS, Galileo, BeiDou

Starlink, OneWeb, Iridium, QZSS, and NavIC do not contribute to the position fix in this application (they are not positioning constellations, or not enabled for that purpose here).

### Satellite Names

In TLE mode, names come directly from the CelesTrak TLE files — these are the official NORAD names (e.g. `GPS BIIR-2 (PRN 13)`, `STARLINK-1234`, `ISS (ZARYA)`).

In simulation mode, names are generated as `"{SYSTEM} PRN {prn}"`.

Hardware receivers do not provide names; the hover panel shows `"SYSTEM PRN n"` as a fallback.

### Simulation vs TLE vs Hardware

| Feature | Simulation | Live TLE | Hardware |
|---------|-----------|---------|---------|
| Real satellite positions | No — approximate Keplerian | Yes — SGP4 propagated | Yes — reported by receiver |
| Sub-satellite lat/lon | Yes | Yes | No |
| Satellite altitude | Yes | Yes | No |
| Satellite names | Generated | Real TLE names | No |
| Internet required | No | Yes (first use) | No |
| GPS hardware required | No | No | Yes |
| Fix uses real observer position | No (fixed at default) | No | Yes |

---

## 15. Repository Structure

```
GPS/
├── main.py                    Entry point; SSL patch, arg parsing, dark theme, window setup
├── requirements.txt           Python package dependencies
├── CLAUDE.md                  Instructions for Claude Code when working in this repo
├── MANUAL.md                  This file
│
├── gps/                       GPS data acquisition and satellite mathematics
│   ├── __init__.py
│   ├── data_models.py         Shared dataclasses: SatelliteInfo, GPSFix, GPSData, etc.
│   ├── receiver.py            GPSReceiver — central data source, runs on QThread
│   ├── simulator.py           GPSSimulator — Keplerian multi-constellation simulator
│   ├── tle_simulator.py       TLESimulator — SGP4 propagator using live CelesTrak data
│   ├── tle_source.py          TLE download, 24h file cache, 4-tier fallback
│   ├── satellites.py          SatelliteDatabase — persistent JSON TLE store (satellites.dat)
│   └── protocols/
│       ├── __init__.py
│       ├── nmea.py            NMEA 0183 parser (GGA, RMC, GSA, GSV, ZDA sentences)
│       ├── ubx.py             u-blox UBX binary parser (NAV-PVT, NAV-SAT messages)
│       └── sirf.py            SiRF III binary state-machine parser
│
├── gui/                       All PyQt6 widgets and rendering
│   ├── __init__.py
│   ├── main_window.py         MainWindow — orchestrates all widgets and threads
│   ├── globe_3d.py            Globe3DWidget — VisPy OpenGL globe
│   ├── display_worker.py      DisplayWorker — background pre-computation thread
│   ├── satellite_table.py     SatelliteTableWidget — sortable satellite list
│   ├── sky_view.py            SkyViewWidget — polar matplotlib sky plot
│   ├── world_map.py           WorldMapWidget — folium/matplotlib world map
│   ├── time_display.py        TimeDisplayWidget — live UTC/GPS/NTP time panel
│   └── sat_hover_widget.py    SatHoverWidget — satellite detail on globe hover
│
├── time_module/               NTP time estimation
│   ├── __init__.py
│   └── ntp_client.py          NTPClient — parallel multi-server NTP with outlier rejection
│
├── utils/                     Shared utilities
│   ├── __init__.py
│   ├── orbital_math.py        WGS-84 constants; Keplerian, ECEF, geodetic, ENU transforms
│   └── log_config.py          Logging setup: rotating file at DEBUG, console at WARNING
│
├── docs/                      Per-module documentation
│   ├── README.md              Index table
│   ├── main.md
│   ├── data-models.md
│   ├── receiver.md
│   ├── simulator.md
│   ├── tle-simulator.md
│   ├── tle-source.md
│   ├── satellites.md
│   ├── protocols.md
│   ├── main-window.md
│   ├── globe-3d.md
│   ├── display-worker.md
│   ├── satellite-table.md
│   ├── sky-view.md
│   ├── world-map.md
│   ├── time-display.md
│   ├── sat-hover-widget.md
│   ├── ntp-client.md
│   ├── orbital-math.md
│   └── log-config.md
│
├── logs/                      Runtime and session logs
│   ├── .gitkeep               Keeps the directory in git
│   ├── *.log                  Application log (runtime, excluded from git)
│   └── *.jsonl                Claude Code session transcripts (tracked)
│
├── tle_cache/                 24-hour TLE file cache (excluded from git)
│   └── <system>.tle           One file per constellation, e.g. gps.tle, starlink.tle
│
└── gps/satellites.dat         Persistent satellite database (excluded from git)
                               Survives cache clearing and network outages
```

### Key File Descriptions

**`gps/data_models.py`**  
The single source of truth for data structures. Every other module imports from here. `SatelliteInfo` carries everything the display layer needs: identity, observer-relative angles, signal quality, and geographic position. `SYSTEM_COLORS` maps each constellation to a hex colour used consistently across every widget.

**`gps/receiver.py`**  
The central data pump. Handles all three input modes — serial hardware with auto-protocol-detection, TLE propagation, and simulation — behind a uniform `data_ready` signal interface. The caller never needs to know which mode is active.

**`gps/simulator.py`**  
A self-contained orbital simulator with a hardcoded almanac covering 228 satellites across 9 constellations. Uses Newton-Raphson Kepler solving from `orbital_math.py`. Useful for development and demonstration with no external dependencies.

**`gps/tle_simulator.py`**  
Produces the most realistic output: real satellites at real positions, updated every second. Uses the `sgp4` library for propagation. Handles the TEME-to-ECEF coordinate transform via GMST rotation, and batches all coordinate arithmetic as numpy operations for efficiency. Large constellations (Starlink, OneWeb) are stride-sampled to preserve global coverage rather than showing only observer-local satellites.

**`gps/tle_source.py`**  
Implements a four-tier data access strategy: fresh file cache → live download + database update → stale cache → persistent database. This means the app degrades gracefully under network outages and picks up from the local store on restart without re-downloading.

**`gps/satellites.py`**  
A JSON file (`satellites.dat`) keyed by NORAD catalog ID. Unlike the flat TLE cache files, this database accumulates across downloads and is never expired — it only grows or updates. Written atomically using `.tmp` + `os.replace()`.

**`gui/display_worker.py`**  
The performance bottleneck for a high-satellite-count app is colour arithmetic, string formatting, and numpy array construction — all done once per frame. `DisplayWorker` moves this off the main thread so Qt can keep the UI responsive. The main thread only calls `set_data()` and `setText()` — operations that complete in microseconds.

**`gui/globe_3d.py`**  
The most complex widget. Key design decisions:
- `depth_test=False` on satellite markers so they render on both hemispheres
- Screen-space pixel-distance hover detection (not angular distance) so hits are accurate at any orbital altitude
- Terrain markers re-parented to scene tail after terrain attach so they always render on top
- Terrain texture generated by cartopy/matplotlib (not `plt` which would conflict with the active Qt backend)

**`utils/orbital_math.py`**  
All WGS-84 geodetic maths in one place, with no Qt or GUI dependencies. Used by both the Keplerian simulator and the TLE batch coordinate transforms.

**`utils/log_config.py`**  
One call in `main.py` configures the entire logging tree. DEBUG-level detail goes to a rotating file; WARNING and above appear in the console. All modules use `logging.getLogger(__name__)` — no explicit configuration needed.

---

## 16. Architecture Reference

### Thread Model

The application uses three QThreads:

```
Main thread (Qt event loop)
    ↑ prepared signal (PreparedFrame)
DisplayWorker thread
    ↑ data_ready signal (GPSData)
GPSReceiver thread  ←→  NTPClient thread (independent)
```

All threads use the `QObject.moveToThread()` pattern — they are not `QThread` subclasses. Signals cross thread boundaries automatically as `QueuedConnection`, which Qt marshals through the event loop safely.

When a source is switched, the old GPSReceiver thread is stopped and a new one started. If the old thread does not exit within 7 seconds (for example, if a TLE download is in progress), it is "parked" — a Python reference is held in `_dying_threads` until `QThread.finished` fires. This prevents Qt from calling `abort()` when the C++ `QThread` object would otherwise be garbage-collected while still running.

### Data Flow Per Frame

1. `GPSReceiver` calls the simulator or parser and emits `data_ready(GPSData)` (~1 Hz).
2. `DisplayWorker.process(GPSData)` runs on its thread:
   - Computes 3D positions and RGBA colours for every satellite (numpy)
   - Sorts and formats the table rows (top 300 by elevation)
   - Filters sky-view satellites (elevation ≥ 0)
   - Throttles sky-view to 1 Hz
   - Emits `prepared(PreparedFrame)`
3. `MainWindow._on_prepared(PreparedFrame)` runs on the main thread:
   - `globe.apply_prepared(pos, col, sats)` → `Markers.set_data()` — no loop
   - `sat_table.apply_rows(rows)` → bulk `QTableWidgetItem` creation
   - Optionally `sky_view.update_satellites(sats)` → matplotlib redraw
   - `time_display.update_gps_time(...)` → `QLabel.setText()`
   - Updates per-system count labels
   - Updates status bar

### TLE Data Lifecycle

```
CelesTrak (HTTPS)
    ↓  download (first use or > 24h old)
tle_cache/<system>.tle  (flat text, 24h TTL)
    ↓  on successful download
gps/satellites.dat  (persistent JSON, no TTL)
    ↓  fallback if cache missing and network unavailable
TLESimulator._satrecs  (in-memory list of Satrec objects)
```

---

## 17. Built with Claude Code

This entire project was created through conversations with **Claude Code** — no code was written by hand. The build happened across multiple sessions, each stored as a `.jsonl` log in the `logs/` directory.

### What Claude Code Did

- Designed the overall architecture from a brief description of requirements
- Wrote all Python source files from scratch
- Fixed rendering bugs (back-hemisphere satellites, hover detection, terrain overlay)
- Identified and resolved thread safety issues (`_park_thread` pattern)
- Refactored the data pipeline to move heavy computation to a background thread
- Added a persistent satellite database to handle unreliable network access
- Set up git and pushed the project to GitHub
- Generated this documentation

### How the Sessions Were Structured

Each session began with Claude reading `CLAUDE.md` to re-establish context, then the user described a problem or feature in plain language. Claude read the relevant source files, proposed a solution, implemented it, and in some cases ran the app to verify. The session logs capture the full reasoning process.

### Reproducing This Workflow

To explore using Claude Code similarly:
1. Install Claude Code: `npm install -g @anthropic/claude-code`
2. Start it in a project directory: `claude`
3. Describe what you want to build
4. Review and approve file edits as they are proposed
5. Test, then describe the next requirement or bug

The session logs in `logs/*.jsonl` are readable JSON Lines — each line is one message turn in the conversation, including all tool calls and responses.
