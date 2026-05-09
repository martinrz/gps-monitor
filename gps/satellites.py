"""Persistent satellite database — accumulates TLE data across server updates.

Stores orbital elements in satellites.dat (JSON) keyed by NORAD catalog ID so
entries merge correctly across downloads rather than duplicating by list position.
Acts as a deep fallback after the 24-hour tle_cache layer.
"""
import json
import logging
import os
import time

log = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'satellites.dat')


def _norad_id(line1: str) -> str:
    return line1[2:7].strip()


class SatelliteDatabase:
    def __init__(self, path: str = _DB_PATH):
        self._path = path
        self._data: dict = {}
        self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                raw = json.load(f)
            if raw.get('version') == 1:
                self._data = raw.get('systems', {})
            total = sum(len(v.get('satellites', {})) for v in self._data.values())
            log.info("Loaded satellite DB: %d systems, %d entries", len(self._data), total)
        except FileNotFoundError:
            self._data = {}
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("Satellite DB corrupted, starting fresh: %s", exc)
            self._data = {}

    def _save(self):
        tmp = self._path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump({'version': 1, 'systems': self._data}, f, separators=(',', ':'))
        os.replace(tmp, self._path)

    def update(self, system: str, tles: list, timestamp: float = None):
        """Merge (name, line1, line2) tuples; replace older entries by NORAD ID."""
        if not tles:
            return
        ts = timestamp or time.time()
        sys_data = self._data.setdefault(system, {'last_download': 0.0, 'satellites': {}})
        sys_data['last_download'] = ts
        sats = sys_data['satellites']
        added = 0
        for name, l1, l2 in tles:
            nid = _norad_id(l1)
            if nid not in sats or sats[nid]['ts'] < ts:
                sats[nid] = {'name': name, 'line1': l1, 'line2': l2, 'ts': ts}
                added += 1
        log.debug("DB merge %s: %d/%d entries updated", system, added, len(tles))
        self._save()

    def get(self, system: str) -> list:
        """Return list of (name, line1, line2) for the given system."""
        sys_data = self._data.get(system)
        if not sys_data:
            return []
        return [(s['name'], s['line1'], s['line2'])
                for s in sys_data['satellites'].values()]

    def last_download(self, system: str) -> float:
        return self._data.get(system, {}).get('last_download', 0.0)

    def count(self, system: str) -> int:
        return len(self._data.get(system, {}).get('satellites', {}))


_db = SatelliteDatabase()


def get_database() -> SatelliteDatabase:
    return _db
