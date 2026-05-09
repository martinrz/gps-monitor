import struct
from typing import Optional
from gps.data_models import GPSData, GPSFix, SatelliteInfo
import time


SYNC_A = 0xA0
SYNC_B = 0xA2
END_A = 0xB0
END_B = 0xB3

MSG_GEODETIC_NAV = 0x29     # 41 decimal
MSG_MEASURED_TRACKER = 0x04


class SiRFParser:
    """State-machine binary parser for SiRF III protocol."""

    SYNC = 0
    LENGTH_HI = 1
    LENGTH_LO = 2
    PAYLOAD = 3
    CHECKSUM_HI = 4
    CHECKSUM_LO = 5
    END_A_STATE = 6
    END_B_STATE = 7

    def __init__(self):
        self._state = self.SYNC
        self._length = 0
        self._payload = bytearray()
        self._checksum = 0
        self._satellites: list = []
        self._current_data = GPSData(protocol="SiRF")

    def feed_byte(self, b: int) -> Optional[GPSData]:
        if self._state == self.SYNC:
            if b == SYNC_A:
                self._state = self.LENGTH_HI
        elif self._state == self.LENGTH_HI:
            if b == SYNC_B:
                self._state = self.LENGTH_LO
                self._length = 0
                self._payload = bytearray()
                self._checksum = 0
            else:
                self._state = self.SYNC
        elif self._state == self.LENGTH_LO:
            self._length = b
            self._state = self.PAYLOAD
        elif self._state == self.PAYLOAD:
            self._payload.append(b)
            self._checksum = (self._checksum + b) & 0x7FFF
            if len(self._payload) == self._length:
                self._state = self.CHECKSUM_HI
        elif self._state == self.CHECKSUM_HI:
            self._recv_cs = b << 8
            self._state = self.CHECKSUM_LO
        elif self._state == self.CHECKSUM_LO:
            self._recv_cs |= b
            self._state = self.END_A_STATE
        elif self._state == self.END_A_STATE:
            if b == END_A:
                self._state = self.END_B_STATE
            else:
                self._state = self.SYNC
        elif self._state == self.END_B_STATE:
            self._state = self.SYNC
            if b == END_B and self._recv_cs == self._checksum:
                return self._dispatch(bytes(self._payload))
        return None

    def feed_bytes(self, data: bytes) -> list:
        results = []
        for b in data:
            result = self.feed_byte(b)
            if result is not None:
                results.append(result)
        return results

    def _dispatch(self, payload: bytes) -> Optional[GPSData]:
        if not payload:
            return None
        msg_id = payload[0]
        if msg_id == MSG_GEODETIC_NAV:
            return self._handle_geodetic_nav(payload)
        elif msg_id == MSG_MEASURED_TRACKER:
            self._handle_tracker(payload)
        return None

    def _handle_geodetic_nav(self, payload: bytes) -> Optional[GPSData]:
        if len(payload) < 91:
            return None
        try:
            nav_valid = struct.unpack_from('>H', payload, 1)[0]
            year = struct.unpack_from('>H', payload, 11)[0]
            month = payload[13]
            day = payload[14]
            hour = payload[15]
            minute = payload[16]
            second = struct.unpack_from('>H', payload, 17)[0] // 1000

            lat = struct.unpack_from('>i', payload, 23)[0] * 1e-7
            lon = struct.unpack_from('>i', payload, 27)[0] * 1e-7
            alt = struct.unpack_from('>i', payload, 31)[0] * 1e-2
            speed = struct.unpack_from('>H', payload, 35)[0] * 1e-2
            heading = struct.unpack_from('>H', payload, 37)[0] * 1e-2
            hdop = payload[89] * 0.2
            num_sats = payload[88]

            fix_quality = 1 if (nav_valid & 0x01) else 0

            self._current_data.fix = GPSFix(
                latitude=lat, longitude=lon, altitude=alt,
                speed=speed, heading=heading,
                fix_quality=fix_quality, num_sats_used=num_sats, hdop=hdop
            )
            self._current_data.gps_time = f"{hour:02d}:{minute:02d}:{second:02d}"
            self._current_data.gps_date = f"{day:02d}/{month:02d}/{year}"
            self._current_data.timestamp = time.time()
            self._current_data.satellites = self._satellites
            return self._current_data
        except struct.error:
            return None

    def _handle_tracker(self, payload: bytes):
        if len(payload) < 3:
            return
        num_channels = payload[1]
        sats = []
        offset = 2
        for _ in range(min(num_channels, 12)):
            if offset + 15 > len(payload):
                break
            try:
                svid = payload[offset]
                azimuth = struct.unpack_from('>H', payload, offset + 1)[0] * 0.3515625   # 360/1024
                elevation = struct.unpack_from('>H', payload, offset + 3)[0] * 0.3515625
                state = struct.unpack_from('>H', payload, offset + 5)[0]
                cno_avg = sum(payload[offset + 7: offset + 15]) / 8.0
                sats.append(SatelliteInfo(
                    prn=svid, azimuth=azimuth % 360,
                    elevation=min(elevation, 90.0),
                    snr=cno_avg, used_in_fix=bool(state & 0x01)
                ))
            except (struct.error, IndexError):
                break
            offset += 15
        self._satellites = sats
