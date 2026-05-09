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
    ├── _run_simulation()   → GPSSimulator (Keplerian almanac, multi-constellation)
    ├── _run_tle_mode()     → TLESimulator (sgp4 propagator, live CelesTrak TLEs)
    └── _connect_to_port()  → NMEAParser / UBXParser / SiRFParser (auto-detected)
         ↓
    data_ready signal (GPSData)
         ↓
    DisplayWorker (QObject on QThread)  ← pre-computes arrays, color math, row tuples
         ↓
    prepared signal (PreparedFrame) → main thread
         ↓
    Globe3DWidget, SatelliteTableWidget, SkyViewWidget, WorldMapWidget,
    TimeDisplayWidget, SatHoverWidget

NTPClient (QObject on QThread) → time_updated signal → TimeDisplayWidget
```

### Key Modules

- **`gps/data_models.py`** — All shared dataclasses: `SatelliteInfo`, `GPSFix`, `GPSData`, `NTPResult`, `TimeEstimate`. Also defines `SYSTEM_COLORS` and `ALL_SYSTEMS` used for constellation filtering throughout the app. `SatelliteInfo.name` carries the human-readable TLE name or a generated label.

- **`gps/receiver.py`** — `GPSReceiver(QObject)`: central data source. Exposes `data_ready`, `status_changed`, `error_occurred` signals. Protocol auto-detection scans baud rates 9600/4800/38400/115200 looking for NMEA (`$GP`/`$GN`/`$GL`), UBX (`\xB5\x62`), or SiRF (`\xA0\xA2`) magic bytes, then falls back to simulation. `_run_tle_mode()` passes `stop_check=lambda: not self._running` to `TLESimulator.preload()` so the download loop can be interrupted between systems.

- **`gps/simulator.py`** — `GPSSimulator`: hardcoded multi-constellation almanac (GPS 31 sats, GLONASS 24, Galileo 27, BeiDou 35, QZSS 4, NavIC 7, Starlink 100). Uses `utils/orbital_math.py` Keplerian mechanics. Populates `SatelliteInfo.name` as `"{system} PRN {prn}"`.

- **`gps/tle_simulator.py`** — `TLESimulator`: uses `sgp4.api.Satrec` to propagate real TLEs. Handles TEME→ECEF coordinate transformation (via GMST rotation) and batched ECEF→az/el computation. Each system is capped at `_MAX_SATS_PER_SYSTEM = 2000`; large constellations are stride-sampled (not elevation-sorted) to preserve global geographic distribution across orbital planes. `preload()` accepts an optional `stop_check` callable checked between system downloads.

- **`gps/tle_source.py`** — Downloads TLEs from CelesTrak, caches to `tle_cache/*.tle` with a 24-hour TTL. Four-tier fallback: fresh cache → download + DB update → stale cache → persistent DB. `TLE_GROUPS` maps system name → `(url_template, key)` tuple. Starlink uses `NAME=STARLINK` because CelesTrak returns 403 on `GROUP=STARLINK`. `QZSS` uses `QZSS-OPS` group.

- **`gps/satellites.py`** — `SatelliteDatabase`: persistent JSON store at `gps/satellites.dat`, keyed by NORAD catalog ID. Merges new TLEs by replacing older entries. Survives cache clears, 24h TTL expiry, and extended outages. Written atomically via `.tmp` + `os.replace`.

- **`utils/orbital_math.py`** — WGS-84 geodetic constants and math: `keplerian_to_ecef()` (Newton-Raphson Kepler solver), `latlon_to_ecef()`, `ecef_to_latlon()` (Bowring iterative), `ecef_to_azel()` (ENU rotation matrix).

- **`utils/log_config.py`** — `setup()` configures the root logger once: `RotatingFileHandler` (1 MB, 5 backups) at DEBUG level to `logs/gps_monitor.log`; `StreamHandler` at WARNING only. Called once in `main.py` before any other import. All modules obtain their logger with `logging.getLogger(__name__)`.

- **`gui/main_window.py`** — `MainWindow(QMainWindow)`: orchestrates everything. Central widget is `Globe3DWidget`. Three docks: satellite table (left), sky view + time display + hover panel (right, vertical splitter), world map (bottom). Two toolbars: GPS source selector + constellation filter buttons with live per-system satellite counts. `_start_threads()` is safe to call multiple times (switching sources): the display worker, NTP thread, and globe/map signal connections are created only once. `_park_thread()` keeps a Python reference to a still-running `QThread` in `_dying_threads` to prevent Qt's fatal `abort()` when the GC destroys a running thread.

- **`gui/display_worker.py`** — `DisplayWorker(QObject)` runs on a dedicated QThread. Receives `GPSData`, pre-computes globe position/color arrays (numpy float32), table row tuples (string + RGB), and filtered sky-view satellite list. Emits `PreparedFrame` for the main thread to apply with fast `set_data()` / `setText()` calls only. Sky view is throttled to 1s intervals; table is capped at 300 rows (top by elevation).

- **`gui/globe_3d.py`** — VisPy `SceneCanvas` with `TurntableCamera`. Earth sphere uses `set_gl_state('translucent', depth_test=True, cull_face=False)` — `cull_face=False` is required so the back hemisphere renders through the transparent front. Satellite markers use `depth_test=False` so they render on both hemispheres regardless of the Earth's depth buffer. Hover detection uses screen-space projection (`get_transform('visual', 'canvas')`) to compute 2D pixel distances, matching dots at any orbital altitude (LEO/MEO/GEO rendered at different visual radii). Terrain toggle generates a 2048×1024 RGBA texture using `cartopy` + `FigureCanvasAgg`; after terrain is attached, marker visuals are re-parented to the tail of the scene so they always render on top. Emits `satellite_hovered` on mouse move, `observer_moved` on right-click drag, `satellite_selected` on double-click.

- **`gui/sat_hover_widget.py`** — `SatHoverWidget(QWidget)`: compact info panel in the right dock. Shows system-colored satellite name at top; two-column detail grid (System, PRN, Elevation, Azimuth, SNR, In-fix, Sub-sat lat/lon, Altitude). Hidden when nothing is hovered. Receives `SatelliteInfo | None` via `show_satellite()`.

- **`gui/satellite_table.py`** — `SatelliteTableWidget(QTableWidget)`: sortable table of all visible satellites. `apply_rows()` fast path accepts pre-computed tuples from `DisplayWorker`. `update_satellites()` legacy path computes colors inline.

- **`gui/sky_view.py`** — Polar matplotlib plot (North up, clockwise). Satellites plotted at (azimuth, 90−elevation); PRN labels annotated. Throttled via `DisplayWorker`.

- **`gui/world_map.py`** — folium HTML map inside `QWebEngineView`. Throttled to 2s refresh. Falls back to matplotlib if WebEngine unavailable. Emits `location_clicked` signal on map click (via JS title-change bridge).

- **`gui/time_display.py`** — Live UTC clock (100ms QTimer), GPS sentence time, NTP weighted-average time with uncertainty and server count, GPS-NTP offset.

- **`time_module/ntp_client.py`** — `NTPClient(QObject)`: queries 8 NTP servers in parallel (ThreadPoolExecutor), outlier-rejects (2σ), computes weighted-average offset and uncertainty. Updates every 30s.

### Thread Safety

`GPSReceiver`, `DisplayWorker`, and `NTPClient` use `moveToThread()` pattern (not subclassing `QThread`). All UI updates happen exclusively on the main thread via Qt's automatic `QueuedConnection` marshalling.

**Critical**: Qt calls `abort()` if a `QThread` C++ object is garbage-collected while its thread is still running. The `_park_thread()` / `_dying_threads` mechanism in `MainWindow` prevents this by holding a Python reference until `finished` fires.

### Constellation System Identifiers

The canonical system strings (used in `SatelliteInfo.system`, `SYSTEM_COLORS`, toolbar buttons, and TLE group keys) are:
`GPS`, `GLONASS`, `GALILEO`, `BEIDOU`, `QZSS`, `NAVIC`, `STARLINK`, `ONEWEB`, `IRIDIUM`, `STATIONS`

`NAVIC` has no CelesTrak TLE group and silently produces zero satellites in TLE mode.

### SNR / Visibility Color Thresholds

- Globe & table: green ≥ 35 dBHz, yellow ≥ 25, orange > 0, dim = 0
- `used_in_fix`: elevation > 10° AND snr > 20 dBHz AND system in `{GPS, GLONASS, GALILEO, BEIDOU}`

### Module Documentation

Per-module docs are in `docs/`. See `docs/README.md` for the index.
