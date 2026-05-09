# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Simulation mode (no hardware required — all panels populate within ~2s)
python main.py --simulate

# Live TLE mode (downloads real satellite data from CelesTrak)
python main.py --tle

# Hardware GPS receiver
python main.py --port /dev/ttyUSB0   # or COM3 on Windows
```

## Installing Dependencies

```bash
pip install -r requirements.txt
pip install cartopy shapely
```

Key packages: PyQt6, PyQt6-WebEngine, vispy, matplotlib, folium, pyserial, pynmea2, pyubx2, ntplib, numpy, sgp4, certifi, cartopy, shapely.

`cartopy` and `shapely` are not in `requirements.txt` but are required for globe coastlines and the Terrain toggle. They install cleanly from PyPI on macOS ARM.

## macOS SSL Certificates

Python on macOS does not trust the system certificate store by default. `main.py` patches `ssl._create_default_https_context` at startup to use certifi's bundle, which fixes all HTTPS downloads (TLE data, cartopy Natural Earth shapefiles). This patch must remain at the top of `main.py` before any network-using imports.

## Architecture Overview

The app is a multi-panel GPS monitoring GUI with three data source modes: Keplerian simulation, live TLE propagation via CelesTrak/sgp4, and real serial hardware (NMEA/UBX/SiRF).

### Data Flow

```
GPSReceiver (QObject on QThread)
    ├── _run_simulation()   → GPSSimulator (Keplerian almanac, ~31 GPS sats)
    ├── _run_tle_mode()     → TLESimulator (sgp4 propagator, live CelesTrak TLEs)
    └── _connect_to_port()  → NMEAParser / UBXParser / SiRFParser (auto-detected)
         ↓
    data_ready signal (GPSData) → Qt event loop → MainWindow slots
         ↓
    SatelliteTableWidget, SkyViewWidget, Globe3DWidget, WorldMapWidget, TimeDisplayWidget

NTPClient (QObject on QThread) → time_updated signal → TimeDisplayWidget
```

### Key Modules

- **`gps/data_models.py`** — All shared dataclasses: `SatelliteInfo`, `GPSFix`, `GPSData`, `NTPResult`, `TimeEstimate`. Also defines `SYSTEM_COLORS` and `ALL_SYSTEMS` used for constellation filtering throughout the app.

- **`gps/receiver.py`** — `GPSReceiver(QObject)`: central data source. Exposes `data_ready`, `status_changed`, `error_occurred` signals. Protocol auto-detection scans baud rates 9600/4800/38400/115200 looking for NMEA (`$GP`/`$GN`/`$GL`), UBX (`\xB5\x62`), or SiRF (`\xA0\xA2`) magic bytes, then falls back to simulation. `_run_tle_mode()` passes `stop_check=lambda: not self._running` to `TLESimulator.preload()` so the download loop can be interrupted between systems.

- **`gps/simulator.py`** — `GPSSimulator`: hardcoded GPS almanac (6 orbital planes × ~5 sats, 26,560 km semi-major axis, 55° inclination). Uses `utils/orbital_math.py` Keplerian mechanics.

- **`gps/tle_simulator.py`** — `TLESimulator`: uses `sgp4.api.Satrec` to propagate real TLEs. Handles TEME→ECEF coordinate transformation (via GMST rotation) and batched ECEF→az/el computation. Each system is capped at `_MAX_SATS_PER_SYSTEM = 400`, sorted by elevation descending, to prevent VisPy and QTableWidget from being overwhelmed by large constellations (Starlink has 10,000+). `preload()` accepts an optional `stop_check` callable checked between system downloads.

- **`gps/tle_source.py`** — Downloads TLEs from CelesTrak, caches to `tle_cache/*.tle` with a 24-hour TTL. `TLE_GROUPS` maps system name → `(url_template, key)` tuple. Most systems use `GROUP=` queries; Starlink uses `NAME=STARLINK` because CelesTrak returns 403 on the `GROUP=STARLINK` endpoint. Uses a module-level `_SSL_CTX` built from certifi for all downloads (15s timeout).

- **`utils/orbital_math.py`** — WGS-84 geodetic constants and math: `keplerian_to_ecef()` (Newton-Raphson Kepler solver), `latlon_to_ecef()`, `ecef_to_latlon()` (Bowring iterative), `ecef_to_azel()` (ENU rotation matrix).

- **`gui/main_window.py`** — `MainWindow(QMainWindow)`: orchestrates everything. Central widget is `Globe3DWidget`. Three docks: satellite table (left), sky view + time display (right, vertical splitter), world map (bottom). Two toolbars: GPS source selector + constellation filter buttons with live per-system satellite counts. `_start_threads()` is safe to call multiple times (switching sources): the NTP thread and globe/map signal connections are created only once. `_park_thread()` keeps a Python reference to a still-running `QThread` in `_dying_threads` to prevent Qt's fatal `abort()` when the GC destroys a running thread — critical for TLE mode where downloads can outlast a 7s stop-wait.

- **`gui/globe_3d.py`** — VisPy `SceneCanvas` with `TurntableCamera`. Earth sphere uses `set_gl_state('translucent', depth_test=True, cull_face=False)` — `cull_face=False` is required so the back hemisphere renders through the transparent front. Coastlines drawn via cartopy Natural Earth 110m shapefiles (downloaded and cached on first use). Terrain toggle generates a 2048×1024 RGBA texture using `cartopy` + `FigureCanvasAgg` (not `plt` — the PyQt6 backend is already active); UV texture coordinates are computed from vertex spherical positions since VisPy's `MeshData` has no `get_texcoords()`. Satellites plotted as `Markers` colored by system (`SYSTEM_COLORS`). Emits `observer_moved` on right-click drag, `satellite_selected` on double-click.

- **`gui/world_map.py`** — folium HTML map inside `QWebEngineView`. Throttled to 2s refresh. Falls back to matplotlib if WebEngine unavailable. Emits `location_clicked` signal.

### Thread Safety

`GPSReceiver` and `NTPClient` use `moveToThread()` pattern (not subclassing `QThread`). All UI updates happen exclusively on the main thread via Qt's automatic `QueuedConnection` marshalling.

**Critical**: Qt calls `abort()` if a `QThread` C++ object is garbage-collected while its thread is still running. This happens when Python replaces `self._gps_thread` or `self._ntp_thread` while the thread is blocked in slow I/O (TLE downloads, NTP queries). The `_park_thread()` / `_dying_threads` mechanism in `MainWindow` prevents this by holding a Python reference until `finished` fires.

### Constellation System Identifiers

The canonical system strings (used in `SatelliteInfo.system`, `SYSTEM_COLORS`, toolbar buttons, and TLE group keys) are:
`GPS`, `GLONASS`, `GALILEO`, `BEIDOU`, `QZSS`, `NAVIC`, `STARLINK`, `ONEWEB`, `IRIDIUM`, `STATIONS`

`QZSS` and `NAVIC` have no CelesTrak TLE group and silently produce zero satellites in TLE mode.

### SNR / Visibility Color Thresholds

- Globe & table: green ≥ 35 dBHz, yellow ≥ 25, orange > 0, red = 0
- `used_in_fix`: elevation > 10° AND snr > 20 dBHz AND system in `{GPS, GLONASS, GALILEO, BEIDOU}`
