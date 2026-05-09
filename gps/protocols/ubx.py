from typing import Optional
import pyubx2
from gps.data_models import GPSData, GPSFix, SatelliteInfo
import time


GNSS_ID_MAP = {0: 'GPS', 1: 'SBAS', 2: 'GALILEO', 3: 'BEIDOU',
               5: 'QZSS', 6: 'GLONASS'}


class UBXParser:
    def __init__(self):
        self._ubx_reader = None
        self._satellites: list = []
        self._current_data = GPSData(protocol="UBX")

    def feed_bytes(self, raw: bytes) -> Optional[GPSData]:
        try:
            msg = pyubx2.UBXReader.parse(raw)
        except Exception:
            return None
        return self._dispatch(msg)

    def _dispatch(self, msg) -> Optional[GPSData]:
        identity = getattr(msg, 'identity', '')
        if identity == 'NAV-PVT':
            return self._handle_nav_pvt(msg)
        elif identity == 'NAV-SAT':
            self._handle_nav_sat(msg)
        return None

    def _handle_nav_pvt(self, msg) -> GPSData:
        try:
            fix_type = getattr(msg, 'fixType', 0)
            lat = getattr(msg, 'lat', 0) * 1e-7
            lon = getattr(msg, 'lon', 0) * 1e-7
            alt = getattr(msg, 'hMSL', 0) * 1e-3
            speed = getattr(msg, 'gSpeed', 0) * 1e-3
            heading = getattr(msg, 'headMot', 0) * 1e-5
            num_sats = getattr(msg, 'numSV', 0)
            pdop = getattr(msg, 'pDOP', 0) * 0.01
            hour = getattr(msg, 'hour', 0)
            minute = getattr(msg, 'min', 0)
            second = getattr(msg, 'sec', 0)
            day = getattr(msg, 'day', 0)
            month = getattr(msg, 'month', 0)
            year = getattr(msg, 'year', 0)

            self._current_data.fix = GPSFix(
                latitude=lat, longitude=lon, altitude=alt,
                speed=speed, heading=heading,
                fix_quality=fix_type, num_sats_used=num_sats, pdop=pdop
            )
            self._current_data.gps_time = f"{hour:02d}:{minute:02d}:{second:02d}"
            self._current_data.gps_date = f"{day:02d}/{month:02d}/{year}"
            self._current_data.timestamp = time.time()
        except AttributeError:
            pass

        self._current_data.satellites = self._satellites
        return self._current_data

    def _handle_nav_sat(self, msg):
        sats = []
        num_svs = getattr(msg, 'numSvs', 0)
        for i in range(1, num_svs + 1):
            try:
                gnss_id = getattr(msg, f'gnssId_{i:02d}', 0)
                sv_id = getattr(msg, f'svId_{i:02d}', 0)
                cno = getattr(msg, f'cno_{i:02d}', 0)
                elev = getattr(msg, f'elev_{i:02d}', 0)
                azim = getattr(msg, f'azim_{i:02d}', 0)
                flags = getattr(msg, f'flags_{i:02d}', 0)
                used = bool(flags & 0x08)
                sats.append(SatelliteInfo(
                    prn=sv_id,
                    elevation=float(elev),
                    azimuth=float(azim),
                    snr=float(cno),
                    used_in_fix=used,
                    system=GNSS_ID_MAP.get(gnss_id, 'GPS')
                ))
            except AttributeError:
                break
        self._satellites = sats
