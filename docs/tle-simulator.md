# gps/tle_simulator.py

`TLESimulator` — multi-constellation SGP4 propagator driven by live CelesTrak TLE data.

## Public API

```python
sim = TLESimulator(lat=51.5, lon=-0.12, alt=10.0)
sim.set_enabled_systems({'GPS', 'STARLINK', 'ONEWEB'})
sim.preload(stop_check=lambda: not running)   # blocks while downloading
data: GPSData = sim.get_gps_data()
```

## `preload(stop_check=None)`

Calls `_ensure_loaded()` for each enabled system in order. `stop_check` is called between systems so the download loop can be aborted cleanly (used by `GPSReceiver._run_tle_mode()`). TLEs are loaded lazily on subsequent calls to `get_gps_data()` for any system not yet loaded.

## `get_gps_data()`

For each enabled system:
1. Propagate all satrecs with `sat.sgp4(jd_int, jd_fr)` — discards error results (`e != 0`).
2. Convert TEME positions to ECEF via GMST rotation (`_batch_teme_to_ecef`).
3. Batch-compute geodetic lat/lon/alt (`_batch_ecef_to_latlon`, Bowring iterative) and observer az/el (`_batch_ecef_to_azel`, ENU matrix).
4. Apply stride-sample cap if `len(system_sats) > _MAX_SATS_PER_SYSTEM` (2000).

## Satellite Cap Strategy

Large constellations (Starlink ~7000, OneWeb ~651) are stride-sampled rather than elevation-sorted. Elevation sort would keep only observer-local satellites; stride sampling across the TLE file order (which groups satellites by launch batch spanning multiple orbital planes) preserves global geographic distribution.

## Coordinate Transforms

| Function | Description |
|----------|-------------|
| `_unix_to_jd()` | Unix timestamp → Julian Date integer + fraction |
| `_gmst_rad()` | Julian Date → Greenwich Mean Sidereal Time, radians |
| `_batch_teme_to_ecef()` | TEME km → ECEF metres via GMST rotation (vectorised) |
| `_batch_ecef_to_latlon()` | ECEF → geodetic lat/lon/alt, Bowring iterative (vectorised) |
| `_batch_ecef_to_azel()` | ECEF → observer az/el via ENU rotation matrix (vectorised) |

## `used_in_fix` Logic

Only GNSS systems (`GPS`, `GLONASS`, `GALILEO`, `BEIDOU`) contribute to the fix: `elevation > 10°` and `snr > 20 dBHz`.
