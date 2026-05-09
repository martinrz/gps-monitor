# gps/satellites.py

`SatelliteDatabase` — persistent JSON store for TLE data. Acts as a deep fallback after the 24-hour file cache layer in `tle_source.py`.

## Storage Format

File: `gps/satellites.dat` (next to this module, excluded from git).

```json
{
  "version": 1,
  "systems": {
    "GPS": {
      "last_download": 1715000000.0,
      "satellites": {
        "12345": {"name": "GPS BIIR-2 (PRN 13)", "line1": "1 ...", "line2": "2 ...", "ts": 1715000000.0}
      }
    }
  }
}
```

Key is the NORAD catalog ID extracted from TLE line 1 characters 2–6.

## Public API

```python
db = get_database()           # module-level singleton
db.update('GPS', tles, timestamp)   # merge (name, line1, line2) list
tles = db.get('GPS')                # returns list of (name, line1, line2)
ts   = db.last_download('GPS')      # float Unix time
n    = db.count('GPS')              # int satellite count
```

## Merge Logic

`update()` replaces an existing entry only if the new entry's timestamp is newer (`sats[nid]['ts'] < ts`). This prevents re-downloading from rolling back to older elements.

## Atomic Write

`_save()` writes to `<path>.tmp` then calls `os.replace()`. On POSIX this is atomic; on Windows it overwrites atomically as of Python 3.3+. The `.tmp` file is listed in `.gitignore`.
