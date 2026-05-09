"""SGP4 satellite propagator using live CelesTrak TLE data."""
import time
import math
import numpy as np

from gps.data_models import GPSData, GPSFix, SatelliteInfo
from gps.tle_source import get_tles, TLE_GROUPS
from utils.orbital_math import latlon_to_ecef, EARTH_RADIUS, EARTH_B

try:
    from sgp4.api import Satrec
    SGP4_AVAILABLE = True
except ImportError:
    SGP4_AVAILABLE = False

_MAX_SATS_PER_SYSTEM = 2000  # cap large LEO constellations; stride-sampled for global coverage

_JD_J2000 = 2451545.0
_JD_UNIX  = 2440587.5   # JD at 1970-01-01 00:00:00 UTC
_GNSS     = {'GPS', 'GLONASS', 'GALILEO', 'BEIDOU'}

TLE_SYSTEMS = tuple(TLE_GROUPS.keys())


def _unix_to_jd(unix: float):
    full = _JD_UNIX + unix / 86400.0
    jd_int = math.floor(full)
    return float(jd_int), full - jd_int


def _gmst_rad(jd_full: float) -> float:
    T = (jd_full - _JD_J2000) / 36525.0
    deg = (280.46061837
           + 360.98564736629 * (jd_full - _JD_J2000)
           + T * T * (0.000387933 - T / 38710000.0)) % 360.0
    return math.radians(deg)


def _batch_teme_to_ecef(r_km: np.ndarray, gmst: float) -> np.ndarray:
    cg, sg = math.cos(gmst), math.sin(gmst)
    ecef = np.empty_like(r_km)
    ecef[:, 0] = (r_km[:, 0] * cg + r_km[:, 1] * sg) * 1000.0
    ecef[:, 1] = (-r_km[:, 0] * sg + r_km[:, 1] * cg) * 1000.0
    ecef[:, 2] = r_km[:, 2] * 1000.0
    return ecef


def _batch_ecef_to_latlon(xyz: np.ndarray):
    x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    lon = np.degrees(np.arctan2(y, x))
    p   = np.sqrt(x**2 + y**2)
    e2  = 1.0 - (EARTH_B / EARTH_RADIUS)**2
    lat = np.arctan2(z, p * (1.0 - e2))
    for _ in range(10):
        N = EARTH_RADIUS / np.sqrt(1.0 - e2 * np.sin(lat)**2)
        lat_new = np.arctan2(z + e2 * N * np.sin(lat), p)
        if np.max(np.abs(lat_new - lat)) < 1e-11:
            lat = lat_new
            break
        lat = lat_new
    N   = EARTH_RADIUS / np.sqrt(1.0 - e2 * np.sin(lat)**2)
    cl  = np.cos(lat)
    sl  = np.sin(lat)
    alt = np.where(np.abs(cl) > 1e-10,
                   p / cl - N,
                   np.abs(z) / np.where(np.abs(sl) > 1e-10, sl, 1e-10) - N * (1.0 - e2))
    return np.degrees(lat), lon, alt


def _batch_ecef_to_azel(sat_ecef: np.ndarray, obs_ecef: np.ndarray,
                        lat_deg: float, lon_deg: float):
    diff = sat_ecef - obs_ecef[np.newaxis, :]
    lat  = math.radians(lat_deg)
    lon  = math.radians(lon_deg)
    sl, cl   = math.sin(lat), math.cos(lat)
    slon, clon = math.sin(lon), math.cos(lon)
    east  = np.array([-slon,    clon,   0.0])
    north = np.array([-sl*clon, -sl*slon, cl])
    up    = np.array([ cl*clon,  cl*slon, sl])
    e  = diff @ east
    n  = diff @ north
    u  = diff @ up
    az = np.degrees(np.arctan2(e, n)) % 360.0
    el = np.degrees(np.arctan2(u, np.sqrt(e**2 + n**2)))
    return az, el


class TLESimulator:
    """Multi-constellation propagator driven by live CelesTrak TLE data."""

    def __init__(self, lat: float = 51.5074, lon: float = -0.1278, alt: float = 10.0):
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self._obs_ecef = latlon_to_ecef(lat, lon, alt)
        self._enabled: set = set(TLE_SYSTEMS)
        self._satrecs: dict = {}     # system → [(name, satrec), ...]

    def set_enabled_systems(self, systems):
        self._enabled = set(s.upper() for s in systems) & set(TLE_SYSTEMS)

    def set_location(self, lat: float, lon: float, alt: float = 10.0):
        self.lat, self.lon, self.alt = lat, lon, alt
        self._obs_ecef = latlon_to_ecef(lat, lon, alt)

    def preload(self, stop_check=None):
        """Eagerly download / read TLEs for all enabled systems."""
        for sys in list(self._enabled):
            if stop_check and stop_check():
                return
            self._ensure_loaded(sys)

    def _ensure_loaded(self, system: str):
        if system in self._satrecs:
            return
        self._satrecs[system] = []
        if not SGP4_AVAILABLE:
            return
        for name, l1, l2 in get_tles(system):
            try:
                self._satrecs[system].append((name, Satrec.twoline2rv(l1, l2)))
            except Exception:
                pass

    def get_gps_data(self) -> GPSData:
        now = time.time()
        jd_int, jd_fr = _unix_to_jd(now)
        gmst = _gmst_rad(jd_int + jd_fr)
        rng  = np.random.default_rng(int(now))

        all_sats = []

        for system in list(self._enabled):
            self._ensure_loaded(system)
            pairs = self._satrecs.get(system, [])
            if not pairs:
                continue

            # Propagate each satellite individually — avoids SatrecArray shape quirks
            valid_r = []
            valid_sats = []
            valid_names = []
            for name, sat in pairs:
                try:
                    e, r, _ = sat.sgp4(jd_int, jd_fr)
                    if e == 0:
                        valid_r.append(r)
                        valid_sats.append(sat)
                        valid_names.append(name)
                except Exception:
                    pass

            if not valid_r:
                continue

            r_good = np.array(valid_r, dtype=np.float64)   # (N, 3) km TEME

            ecef                   = _batch_teme_to_ecef(r_good, gmst)
            s_lats, s_lons, s_alts = _batch_ecef_to_latlon(ecef)
            azs, els               = _batch_ecef_to_azel(ecef, self._obs_ecef, self.lat, self.lon)
            noise                  = rng.standard_normal(len(valid_r)) * 1.5

            system_sats = []
            for i, sat in enumerate(valid_sats):
                el = float(els[i])
                snr = max(15.0, min(52.0, 20.0 + el * 0.4 + noise[i])) if el > 0 else 0.0

                system_sats.append(SatelliteInfo(
                    prn=sat.satnum,
                    elevation=round(el, 1),
                    azimuth=round(float(azs[i]) % 360, 1),
                    snr=round(snr, 1),
                    used_in_fix=(el > 10.0 and snr > 20.0 and system in _GNSS),
                    system=system,
                    name=valid_names[i],
                    sat_lat=round(float(s_lats[i]), 3),
                    sat_lon=round(float(s_lons[i]), 3),
                    altitude_km=round(float(s_alts[i]) / 1000.0, 1),
                ))

            if len(system_sats) > _MAX_SATS_PER_SYSTEM:
                # Stride-sample across TLE file order rather than sorting by elevation.
                # Elevation sort would keep only observer-local sats; stride-sampling
                # preserves global geographic distribution across orbital planes.
                step = max(1, len(system_sats) // _MAX_SATS_PER_SYSTEM)
                system_sats = system_sats[::step][:_MAX_SATS_PER_SYSTEM]

            all_sats.extend(system_sats)

        visible     = [s for s in all_sats if s.used_in_fix]
        fix_quality = 1 if len(visible) >= 4 else 0

        t      = time.gmtime(now)
        active = sorted(set(s.system for s in visible))
        proto  = 'TLE+' + '+'.join(a[:3] for a in active) if active else 'TLE'

        return GPSData(
            timestamp=now,
            gps_time=f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}",
            gps_date=f"{t.tm_mday:02d}/{t.tm_mon:02d}/{t.tm_year}",
            fix=GPSFix(
                latitude=self.lat, longitude=self.lon, altitude=self.alt,
                speed=0.0, heading=0.0,
                pdop=1.4 if fix_quality else 99.0,
                hdop=1.2 if fix_quality else 99.0,
                vdop=1.8 if fix_quality else 99.0,
                fix_quality=fix_quality,
                num_sats_used=len(visible)
            ),
            satellites=all_sats,
            protocol=proto,
        )
