# gps/tle_source.py

TLE download and caching layer. Provides `get_tles(system) -> list[(name, line1, line2)]`.

## Cache Tiers (in priority order)

1. **Fresh file cache** (`tle_cache/<system>.tle`) — used if mtime < 24 h.
2. **Live download** from CelesTrak — on success, writes the cache file and calls `SatelliteDatabase.update()`.
3. **Stale file cache** — used if the download fails but the old cache file exists.
4. **Persistent database** (`gps/satellites.dat`) — survives cache clearing and extended outages.

## `TLE_GROUPS`

Maps system identifier → `(url_template, key)`:

| System | Endpoint | Key |
|--------|----------|-----|
| GPS | GROUP= | GPS-OPS |
| GLONASS | GROUP= | GLO-OPS |
| GALILEO | GROUP= | GALILEO |
| BEIDOU | GROUP= | BEIDOU |
| QZSS | GROUP= | QZSS-OPS |
| STARLINK | NAME= | STARLINK |
| ONEWEB | GROUP= | ONEWEB |
| IRIDIUM | GROUP= | IRIDIUM-NEXT |
| STATIONS | GROUP= | STATIONS |

Starlink uses `NAME=STARLINK` because `GROUP=STARLINK` returns HTTP 403 from CelesTrak.

## SSL

A module-level `_SSL_CTX` is built from certifi's CA bundle at import time. If certifi is unavailable, `_SSL_CTX = None` (urllib falls back to system certs). All downloads use a 15 s timeout.

## `_parse(data)`

Parses raw TLE text. Iterates line-by-line; a valid triplet requires `lines[i+1]` to start with `1 ` and `lines[i+2]` to start with `2 `. Malformed or mixed-format content is skipped safely.
