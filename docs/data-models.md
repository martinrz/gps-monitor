# gps/data_models.py

Shared dataclasses and constants used across the entire application. No logic — only data definitions.

## Constants

### `SYSTEM_COLORS`
`dict[str, str]` — Maps constellation identifier to hex colour string.  
Keys: `GPS`, `GLONASS`, `GALILEO`, `BEIDOU`, `QZSS`, `NAVIC`, `STARLINK`, `ONEWEB`, `IRIDIUM`, `STATIONS`, `SIM`, `UNKNOWN`.

### `ALL_SYSTEMS`
Tuple of the ten canonical system strings used for constellation filtering (excludes `SIM` and `UNKNOWN`).

## Dataclasses

### `SatelliteInfo`

| Field | Type | Description |
|-------|------|-------------|
| `prn` | `int` | Satellite PRN / NORAD catalogue number |
| `elevation` | `float` | Observer-relative elevation, degrees |
| `azimuth` | `float` | Observer-relative azimuth, degrees |
| `snr` | `float` | Signal-to-noise ratio, dBHz (0 = not tracking) |
| `used_in_fix` | `bool` | Contributed to the position fix |
| `system` | `str` | Constellation identifier (one of `SYSTEM_COLORS` keys) |
| `name` | `str` | Human-readable label — TLE name or `"{system} PRN {prn}"` |
| `sat_lat` | `float \| None` | Sub-satellite geodetic latitude, degrees |
| `sat_lon` | `float \| None` | Sub-satellite geodetic longitude, degrees |
| `altitude_km` | `float \| None` | Altitude above Earth surface, km |

`sat_lat`, `sat_lon`, `altitude_km` are populated by simulators; hardware parsers leave them `None`.

### `GPSFix`

Observer position fix from the GPS receiver.

| Field | Type | Description |
|-------|------|-------------|
| `latitude` | `float` | Decimal degrees, positive N |
| `longitude` | `float` | Decimal degrees, positive E |
| `altitude` | `float` | Metres MSL |
| `speed` | `float` | m/s |
| `heading` | `float` | Degrees true |
| `pdop / hdop / vdop` | `float` | Dilution of precision values |
| `fix_quality` | `int` | 0=no fix, 1=GPS, 2=DGPS, 4=RTK |
| `num_sats_used` | `int` | Satellites contributing to the fix |

### `GPSData`

One complete snapshot emitted by `GPSReceiver` each second.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `float` | Unix time of this snapshot |
| `gps_time` | `str \| None` | `HH:MM:SS.ss` UTC from GPS |
| `gps_date` | `str \| None` | `DD/MM/YYYY` from GPS |
| `fix` | `GPSFix \| None` | Position fix (None if no lock) |
| `satellites` | `list[SatelliteInfo]` | All tracked satellites |
| `protocol` | `str` | `NMEA`, `UBX`, `SiRF`, `SIM`, `TLE+...` |
| `raw_sentences` | `list[str]` | Raw protocol sentences (hardware only) |

### `NTPResult`

Single server query result from `NTPClient`.

### `TimeEstimate`

Weighted multi-server NTP result emitted by `NTPClient`.

| Field | Type | Description |
|-------|------|-------------|
| `utc_time` | `float` | Best-estimate Unix UTC |
| `uncertainty_ms` | `float` | 1σ uncertainty, milliseconds |
| `contributing_servers` | `int` | Servers included after outlier rejection |
| `gps_offset_ms` | `float \| None` | GPS time minus NTP, ms |
| `method` | `str` | Always `"NTP"` |
