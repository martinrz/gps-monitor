import time
import numpy as np
from gps.data_models import GPSData, GPSFix, SatelliteInfo, ALL_SYSTEMS
from utils.orbital_math import keplerian_to_ecef, ecef_to_azel, latlon_to_ecef, ecef_to_latlon

GPS_EPOCH_UNIX = 315_964_800  # GPS epoch = Jan 6 1980 00:00:00 UTC

# ---------------------------------------------------------------------------
# Full multi-constellation almanac
# Each row: (system, prn, sma_m, ecc, inc_deg, raan_deg, arg_perigee_deg, mean_anomaly_deg)
# ---------------------------------------------------------------------------

def _build_almanac():
    rows = []

    # --- GPS: 31 sats, 6 planes (RAAN 0/60/120/180/240/300°), SMA=26,560 km, inc=55° ---
    _gps = [
        (0,  1,   0.0,  0.0), (0,  2,  72.0, 10.0), (0,  3, 144.0, 20.0),
        (0,  4, 216.0,  5.0), (0,  5, 288.0, 15.0),
        (1,  6,  30.0,  0.0), (1,  7, 102.0, 10.0), (1,  8, 174.0, 20.0),
        (1,  9, 246.0,  5.0), (1, 10, 318.0, 15.0),
        (2, 11,  60.0,  0.0), (2, 12, 132.0, 10.0), (2, 13, 204.0, 20.0),
        (2, 14, 276.0,  5.0), (2, 15, 348.0, 15.0),
        (3, 16,  45.0,  0.0), (3, 17, 117.0, 10.0), (3, 18, 189.0, 20.0),
        (3, 19, 261.0,  5.0), (3, 20, 333.0, 15.0),
        (4, 21,  15.0,  0.0), (4, 22,  87.0, 10.0), (4, 23, 159.0, 20.0),
        (4, 24, 231.0,  5.0), (4, 25, 303.0, 15.0),
        (5, 26,  55.0,  0.0), (5, 27, 127.0, 10.0), (5, 28, 199.0, 20.0),
        (5, 29, 271.0,  5.0), (5, 30, 343.0, 15.0), (5, 31,  25.0, 25.0),
    ]
    gps_raans = [0, 60, 120, 180, 240, 300]
    for plane, prn, ma, ap in _gps:
        rows.append(('GPS', prn, 26_560_000, 0.010, 55.0, gps_raans[plane], ap, ma))

    # --- GLONASS: 24 sats, 3 planes (RAAN 0/120/240°), SMA=25,508 km, inc=64.8° ---
    for plane in range(3):
        for slot in range(8):
            prn  = 65 + plane * 8 + slot
            ma   = (slot * 45.0 + plane * 15.0) % 360
            rows.append(('GLONASS', prn, 25_508_000, 0.001, 64.8, plane * 120.0, 0.0, ma))

    # --- Galileo: 27 sats, 3 planes (RAAN 0/120/240°), SMA=29,600 km, inc=56° ---
    for plane in range(3):
        for slot in range(9):
            prn = 301 + plane * 9 + slot
            ma  = (slot * 40.0 + plane * 13.0) % 360
            rows.append(('GALILEO', prn, 29_599_870, 0.0002, 56.0, plane * 120.0, 0.0, ma))

    # --- BeiDou MEO: 27 sats, 3 planes, SMA=27,906 km, inc=55° ---
    for plane in range(3):
        for slot in range(9):
            prn = 401 + plane * 9 + slot
            ma  = (slot * 40.0 + plane * 13.0) % 360
            rows.append(('BEIDOU', prn, 27_906_000, 0.001, 55.0, plane * 120.0, 0.0, ma))

    # --- BeiDou IGSO: 3 sats at geosynchronous altitude, inclined 55° ---
    GEO_SMA = 42_164_200
    for i, raan in enumerate([80.0, 110.5, 140.0]):
        rows.append(('BEIDOU', 430 + i, GEO_SMA, 0.001, 55.0, raan, 0.0, i * 120.0))

    # --- BeiDou GEO: 5 sats truly geostationary, inc=0 ---
    for i, lon in enumerate([80.0, 110.5, 140.0, 84.0, 160.0]):
        rows.append(('BEIDOU', 433 + i, GEO_SMA, 0.0, 0.0, lon, 0.0, 0.0))

    # --- QZSS: 3 IGSO + 1 GEO, primarily covering Japan/Asia-Pacific ---
    # IGSO with high eccentricity gives figure-8 ground track
    rows.append(('QZSS', 193, GEO_SMA, 0.075, 43.0, 135.0, 270.0, 270.0))
    rows.append(('QZSS', 194, GEO_SMA, 0.075, 43.0, 135.0, 270.0,  30.0))
    rows.append(('QZSS', 195, GEO_SMA, 0.075, 43.0, 135.0, 270.0, 150.0))
    rows.append(('QZSS', 196, GEO_SMA, 0.000,  0.0, 127.0,   0.0,   0.0))  # GEO

    # --- NavIC / IRNSS: 3 GEO + 4 IGSO, covering India/South Asia ---
    for prn, lon in [(801, 32.5), (802, 83.0), (803, 131.5)]:
        rows.append(('NAVIC', prn, GEO_SMA, 0.0, 0.0, lon, 0.0, 0.0))
    for i, (raan, ma) in enumerate([(55.0, 0.0), (111.75, 0.0), (55.0, 180.0), (111.75, 180.0)]):
        rows.append(('NAVIC', 804 + i, GEO_SMA, 0.0, 29.0, raan, 0.0, ma))

    # --- Starlink Shell 1: 550 km altitude, inc=53°, 20 planes × 5 sats = 100 sats ---
    STARLINK_SMA = 6_921_000
    for plane in range(20):
        raan = plane * 18.0
        for slot in range(5):
            prn = 1001 + plane * 5 + slot
            ma  = (slot * 72.0 + plane * 14.4) % 360
            rows.append(('STARLINK', prn, STARLINK_SMA, 0.0001, 53.0, raan, 0.0, ma))

    return rows


FULL_ALMANAC = _build_almanac()


class GPSSimulator:
    """Simulates a multi-constellation GNSS receiver using Keplerian mechanics."""

    def __init__(self, lat: float = 51.5074, lon: float = -0.1278, alt: float = 10.0):
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self._obs_ecef = latlon_to_ecef(lat, lon, alt)
        self._enabled = set(ALL_SYSTEMS)

    def set_enabled_systems(self, systems):
        self._enabled = set(s.upper() for s in systems)

    def set_location(self, lat: float, lon: float, alt: float = 10.0):
        self.lat, self.lon, self.alt = lat, lon, alt
        self._obs_ecef = latlon_to_ecef(lat, lon, alt)

    def get_gps_data(self) -> GPSData:
        now = time.time()
        gps_t = (now - GPS_EPOCH_UNIX) % (7 * 86400)

        satellites = []
        for system, prn, sma, ecc, inc, raan, ap, ma in FULL_ALMANAC:
            if system not in self._enabled:
                continue
            try:
                sat_ecef = keplerian_to_ecef(sma, ecc, inc, raan, ap, ma, gps_t)
                az, el = ecef_to_azel(sat_ecef, self._obs_ecef, self.lat, self.lon)
                s_lat, s_lon, s_alt_m = ecef_to_latlon(sat_ecef)
            except Exception:
                continue

            if el > 0:
                snr = 20.0 + el * 0.4 + np.random.normal(0, 1.5)
                snr = max(15.0, min(52.0, snr))
            else:
                snr = 0.0

            satellites.append(SatelliteInfo(
                prn=prn,
                elevation=round(el, 1),
                azimuth=round(az % 360, 1),
                snr=round(snr, 1),
                used_in_fix=(el > 10.0 and snr > 20.0),
                system=system,
                name=f"{system} PRN {prn}",
                sat_lat=round(s_lat, 3),
                sat_lon=round(s_lon, 3),
                altitude_km=round(s_alt_m / 1000.0, 1),
            ))

        visible = [s for s in satellites if s.used_in_fix]
        fix_quality = 1 if len(visible) >= 4 else 0

        t = time.gmtime(now)
        fix = GPSFix(
            latitude=self.lat, longitude=self.lon, altitude=self.alt,
            speed=0.0, heading=0.0,
            pdop=1.4 if fix_quality else 99.0,
            hdop=1.2 if fix_quality else 99.0,
            vdop=1.8 if fix_quality else 99.0,
            fix_quality=fix_quality,
            num_sats_used=len(visible)
        )

        # Multi-constellation label
        active = sorted(set(s.system for s in visible))
        protocol = '+'.join(a[:3] for a in active) if active else 'SIM'

        return GPSData(
            timestamp=now,
            gps_time=f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}",
            gps_date=f"{t.tm_mday:02d}/{t.tm_mon:02d}/{t.tm_year}",
            fix=fix,
            satellites=satellites,
            protocol=protocol
        )
