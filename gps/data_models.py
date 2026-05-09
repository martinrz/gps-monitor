from dataclasses import dataclass, field
from typing import Optional
import time

SYSTEM_COLORS = {
    'GPS':      '#22cc44',
    'GLONASS':  '#4488ff',
    'GALILEO':  '#ff8822',
    'BEIDOU':   '#ff3344',
    'QZSS':     '#cc44ff',
    'NAVIC':    '#22cccc',
    'STARLINK': '#bbbbbb',
    'ONEWEB':   '#ff9933',
    'IRIDIUM':  '#aaddff',
    'STATIONS': '#ff44ff',
    'SIM':      '#22cc44',
    'UNKNOWN':  '#888888',
}

ALL_SYSTEMS = ('GPS', 'GLONASS', 'GALILEO', 'BEIDOU', 'QZSS', 'NAVIC', 'STARLINK',
               'ONEWEB', 'IRIDIUM', 'STATIONS')


@dataclass
class SatelliteInfo:
    prn: int
    elevation: float        # degrees, observer-relative
    azimuth: float          # degrees, observer-relative
    snr: float              # dBHz, 0 if not tracking
    used_in_fix: bool = False
    system: str = "GPS"
    name: str = ""                       # human-readable label (TLE name or generated)
    # Geographic position (set by simulator; None for hardware receivers)
    sat_lat: Optional[float] = None     # geodetic latitude, degrees
    sat_lon: Optional[float] = None     # geodetic longitude, degrees
    altitude_km: Optional[float] = None # altitude above surface, km


@dataclass
class GPSFix:
    latitude: float         # decimal degrees, positive N
    longitude: float        # decimal degrees, positive E
    altitude: float         # meters MSL
    speed: float            # m/s
    heading: float          # degrees true
    pdop: float = 0.0
    hdop: float = 0.0
    vdop: float = 0.0
    fix_quality: int = 0    # 0=no fix, 1=GPS, 2=DGPS, 4=RTK
    num_sats_used: int = 0


@dataclass
class GPSData:
    timestamp: float = field(default_factory=time.time)
    gps_time: Optional[str] = None      # HH:MM:SS.ss UTC
    gps_date: Optional[str] = None      # DD/MM/YYYY
    fix: Optional[GPSFix] = None
    satellites: list = field(default_factory=list)  # list[SatelliteInfo]
    protocol: str = "UNKNOWN"
    raw_sentences: list = field(default_factory=list)


@dataclass
class NTPResult:
    server: str
    offset: float           # seconds
    delay: float            # seconds (round-trip)
    stratum: int
    success: bool = True
    error: str = ""


@dataclass
class TimeEstimate:
    utc_time: float                     # Unix timestamp
    uncertainty_ms: float               # milliseconds, 1σ
    contributing_servers: int = 0
    gps_offset_ms: Optional[float] = None   # GPS minus NTP, ms
    method: str = "NTP"
