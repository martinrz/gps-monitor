# gui/display_worker.py

`DisplayWorker(QObject)` — background thread that pre-computes all display data so the main thread only executes fast widget-apply calls.

## Purpose

The main thread must not block. Per-satellite loops, numpy array construction, color arithmetic, and string formatting all happen here, off the event loop.

## `PreparedFrame` Dataclass

| Field | Type | Description |
|-------|------|-------------|
| `gps_data` | `GPSData` | Original snapshot (for fix info, protocol, etc.) |
| `globe_pos` | `np.ndarray (N, 3) float32` | 3D positions on the unit sphere (scaled by visual radius) |
| `globe_col` | `np.ndarray (N, 4) float32` | RGBA colours per satellite |
| `table_rows` | `list[tuple]` | `(prn, system, el, az, snr, used, bg_rgb, fg_rgb)` tuples |
| `sky_sats` | `list[SatelliteInfo]` | Satellites at elevation ≥ 0, or `[]` if sky update skipped |
| `update_sky` | `bool` | Whether this frame carries a fresh sky-view satellite list |

## Throttling

- **Sky view**: redrawn at most every `_SKY_INTERVAL = 1.0` s. When skipped, `sky_sats=[]` and `update_sky=False`.
- **Table**: capped at `_TABLE_MAX = 300` rows, sorted by elevation descending. The globe always receives the full dataset.

## Signal

`prepared(object)` — emits a `PreparedFrame`. Connected to `MainWindow._on_prepared()` via `QueuedConnection`.

## Visual Radius Tiers

Matches `globe_3d._vis_radius()`:

| Altitude | Visual radius |
|----------|--------------|
| < 2,000 km (LEO) | 1.12 |
| 2,000–30,000 km (MEO) | 1.80 |
| > 30,000 km (GEO/HEO) | 2.25 |

## Color Logic

Computed from `SYSTEM_COLORS` hex → RGBA:

| Condition | Alpha |
|-----------|-------|
| elevation > 0 and SNR ≥ 25 | 1.0 |
| elevation > 0 | 0.65 |
| below horizon | 0.22 |

Table background/foreground is scaled from the system colour:

| Condition | BG scale | FG scale |
|-----------|----------|----------|
| SNR ≥ 35 | 0.28 | 1.0 |
| SNR ≥ 25 | 0.18 | 0.85 |
| SNR > 0, el > 0 | 0.12 | 0.65 |
| below horizon / no signal | 0.12 | 0.40 |
