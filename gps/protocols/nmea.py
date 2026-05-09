from typing import Optional
import pynmea2
from gps.data_models import GPSData, GPSFix, SatelliteInfo


class NMEAParser:
    def __init__(self):
        # Buffer keyed by (talker, total_msgs) -> {msg_num: sentence}
        self._gsv_buffer: dict = {}
        self._satellites: dict = {}     # prn -> SatelliteInfo
        self._current_data = GPSData(protocol="NMEA")

    def feed(self, line: str) -> Optional[GPSData]:
        line = line.strip()
        if not line.startswith('$'):
            return None
        try:
            msg = pynmea2.parse(line)
        except (pynmea2.ParseError, pynmea2.ChecksumError):
            return None

        sentence_type = msg.sentence_type
        if sentence_type in ('GGA', 'RMC', 'GNS'):
            self._handle_fix(msg)
        elif sentence_type == 'GSA':
            self._handle_gsa(msg)
        elif sentence_type == 'GSV':
            self._handle_gsv(msg)
            return None     # wait until flush
        elif sentence_type == 'ZDA':
            self._handle_zda(msg)

        data = self._current_data
        data.satellites = list(self._satellites.values())
        return data

    def _handle_fix(self, msg):
        try:
            lat = msg.latitude if hasattr(msg, 'latitude') else None
            lon = msg.longitude if hasattr(msg, 'longitude') else None
            if lat is None or lon is None:
                return

            alt = float(getattr(msg, 'altitude', 0) or 0)
            speed = float(getattr(msg, 'spd_over_grnd', 0) or 0) * 0.5144   # knots -> m/s
            heading = float(getattr(msg, 'true_course', 0) or 0)

            quality_map = {'A': 1, 'D': 2, 'E': 0, 'N': 0, 'S': 3}
            fix_q = getattr(msg, 'gps_qual', None) or getattr(msg, 'mode_indicator', None)
            if isinstance(fix_q, str):
                fix_q = quality_map.get(fix_q, 1)
            else:
                fix_q = int(fix_q or 0)

            num_sats = int(getattr(msg, 'num_sats', 0) or 0)
            hdop = float(getattr(msg, 'horizontal_dil', 0) or 0)

            self._current_data.fix = GPSFix(
                latitude=lat, longitude=lon, altitude=alt,
                speed=speed, heading=heading,
                fix_quality=fix_q, num_sats_used=num_sats, hdop=hdop
            )
            ts = getattr(msg, 'timestamp', None)
            if ts:
                self._current_data.gps_time = str(ts)
        except (AttributeError, ValueError, TypeError):
            pass

    def _handle_gsa(self, msg):
        if self._current_data.fix:
            try:
                pdop = float(getattr(msg, 'pdop', 0) or 0)
                hdop = float(getattr(msg, 'hdop', 0) or 0)
                vdop = float(getattr(msg, 'vdop', 0) or 0)
                self._current_data.fix.pdop = pdop
                self._current_data.fix.hdop = hdop
                self._current_data.fix.vdop = vdop
            except (AttributeError, ValueError):
                pass

        used_prns = set()
        for i in range(2, 14):
            field_name = f'sv_id0{i:d}' if i < 10 else f'sv_id{i:d}'
            try:
                prn_str = getattr(msg, f'sv_id0{i-1:d}', None) if i < 10 else None
                # pynmea2 GSA fields are sv_id01 to sv_id12
                pass
            except AttributeError:
                pass
        # Mark used sats
        for j in range(1, 13):
            try:
                prn_str = msg.data[j + 1]   # GSA fields offset
                if prn_str:
                    used_prns.add(int(prn_str))
            except (IndexError, ValueError):
                pass
        for prn, sat in self._satellites.items():
            sat.used_in_fix = prn in used_prns

    def _handle_gsv(self, msg):
        try:
            talker = msg.talker
            total_msgs = int(msg.num_messages)
            msg_num = int(msg.msg_num)
            key = (talker, total_msgs)

            if key not in self._gsv_buffer:
                self._gsv_buffer[key] = {}
            self._gsv_buffer[key][msg_num] = msg

            if msg_num == total_msgs:
                # Flush complete group
                system_map = {'GP': 'GPS', 'GL': 'GLONASS', 'GA': 'GALILEO',
                              'GB': 'BEIDOU', 'GN': 'GPS'}
                system = system_map.get(talker, 'GPS')

                for m in sorted(self._gsv_buffer[key].values(),
                                key=lambda x: int(x.msg_num)):
                    for i in range(4):
                        try:
                            prn = int(m.data[4 + i * 4])
                            el = float(m.data[5 + i * 4] or 0)
                            az = float(m.data[6 + i * 4] or 0)
                            snr_raw = m.data[7 + i * 4]
                            snr = float(snr_raw) if snr_raw else 0.0
                            self._satellites[prn] = SatelliteInfo(
                                prn=prn, elevation=el, azimuth=az,
                                snr=snr, system=system
                            )
                        except (IndexError, ValueError, TypeError):
                            break
                del self._gsv_buffer[key]
                data = self._current_data
                data.satellites = list(self._satellites.values())
                return data
        except (AttributeError, ValueError):
            pass
        return None

    def _handle_zda(self, msg):
        try:
            self._current_data.gps_time = str(msg.timestamp)
            d, mo, y = msg.day, msg.month, msg.year
            self._current_data.gps_date = f"{d:02d}/{mo:02d}/{y}"
        except AttributeError:
            pass
