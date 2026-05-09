"""Download and cache TLE data from CelesTrak (24-hour refresh)."""
import os
import ssl
import time
import urllib.request

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = None

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tle_cache')
CACHE_TTL  = 86400  # seconds

_GROUP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP={key}&FORMAT=TLE"
_NAME_URL  = "https://celestrak.org/NORAD/elements/gp.php?NAME={key}&FORMAT=TLE"

# (url_template, key) — GROUP= works for most; NAME= used where GROUP returns 403
TLE_GROUPS = {
    'GPS':      (_GROUP_URL, 'GPS-OPS'),
    'GLONASS':  (_GROUP_URL, 'GLO-OPS'),
    'GALILEO':  (_GROUP_URL, 'GALILEO'),
    'BEIDOU':   (_GROUP_URL, 'BEIDOU'),
    'QZSS':     (_GROUP_URL, 'QZSS-OPS'),
    'STARLINK': (_NAME_URL,  'STARLINK'),
    'ONEWEB':   (_GROUP_URL, 'ONEWEB'),
    'IRIDIUM':  (_GROUP_URL, 'IRIDIUM-NEXT'),
    'STATIONS': (_GROUP_URL, 'STATIONS'),
}


def _cache_path(system: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{system.lower()}.tle")


def _download(system: str) -> str:
    entry = TLE_GROUPS.get(system)
    if not entry:
        return ""
    url_template, key = entry
    url = url_template.format(key=key)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GPS-Monitor/1.0'})
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception:
        return ""


def get_tles(system: str) -> list:
    """Return list of (name, line1, line2).  Downloads if cache is stale or absent."""
    from gps.satellites import get_database
    db = get_database()

    path = _cache_path(system)

    # 1. Fresh cache (< 24h)
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_TTL:
        with open(path, 'r') as f:
            return _parse(f.read())

    # 2. Download from server; persist to database on success
    data = _download(system)
    if data and len(data) > 100:
        with open(path, 'w') as f:
            f.write(data)
        tles = _parse(data)
        db.update(system, tles)
        return tles

    # 3. Stale cache file
    if os.path.exists(path):
        with open(path, 'r') as f:
            return _parse(f.read())

    # 4. Persistent database — survives cache clearing and extended outages
    db_tles = db.get(system)
    if db_tles:
        return db_tles

    return []


def _parse(data: str) -> list:
    lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
    result = []
    i = 0
    while i + 2 <= len(lines) - 1:
        name = lines[i]
        l1   = lines[i + 1]
        l2   = lines[i + 2]
        if l1.startswith('1 ') and l2.startswith('2 '):
            result.append((name, l1, l2))
            i += 3
        else:
            i += 1
    return result
