"""Background worker: pre-computes display data so the main thread only does fast widget-apply ops."""
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

log = logging.getLogger(__name__)

from gps.data_models import GPSData, GPSFix, SYSTEM_COLORS


def _vis_radius(alt_km) -> float:
    if alt_km is None or alt_km < 2_000:
        return 1.12
    if alt_km < 30_000:
        return 1.80
    return 2.25


def _hex_to_rgba(hex_color: str, alpha: float) -> tuple:
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, alpha)


def _hex_to_rgb_bytes(hex_color: str) -> tuple:
    h = hex_color.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


@dataclass
class PreparedFrame:
    gps_data: GPSData
    globe_pos: Optional[np.ndarray] = None      # (N, 3) float32
    globe_col: Optional[np.ndarray] = None      # (N, 4) float32
    table_rows: list = field(default_factory=list)
    sky_sats: list = field(default_factory=list)
    update_sky: bool = True


class DisplayWorker(QObject):
    """Runs on a dedicated QThread.  Receives GPSData, pre-computes all display
    arrays, and emits PreparedFrame for the main thread to apply quickly."""

    prepared = pyqtSignal(object)   # PreparedFrame

    _SKY_INTERVAL = 1.0             # seconds between matplotlib sky view redraws
    _TABLE_MAX    = 300             # table rows capped; globe always gets full dataset

    def __init__(self):
        super().__init__()
        self._last_sky_update = 0.0

    @pyqtSlot(object)
    def process(self, gps_data: GPSData):
        try:
            self._process(gps_data)
        except Exception as exc:
            log.exception("Display worker error: %s", exc)

    def _process(self, gps_data: GPSData):
        sats = gps_data.satellites

        # --- Globe geometry (per-satellite loop off main thread) ---
        positions = []
        colors = []
        for sat in sats:
            r = _vis_radius(sat.altitude_km)
            if sat.sat_lat is not None and sat.sat_lon is not None:
                lat = math.radians(sat.sat_lat)
                lon = math.radians(sat.sat_lon)
                x = r * math.cos(lat) * math.cos(lon)
                y = r * math.cos(lat) * math.sin(lon)
                z = r * math.sin(lat)
            else:
                az = math.radians(sat.azimuth)
                el = math.radians(sat.elevation)
                x = r * math.cos(el) * math.sin(az)
                y = r * math.cos(el) * math.cos(az)
                z = r * math.sin(el)
            positions.append((x, y, z))
            hex_c = SYSTEM_COLORS.get(sat.system, '#888888')
            if sat.elevation > 0 and sat.snr >= 25:
                colors.append(_hex_to_rgba(hex_c, 1.0))
            elif sat.elevation > 0:
                colors.append(_hex_to_rgba(hex_c, 0.65))
            else:
                colors.append(_hex_to_rgba(hex_c, 0.22))

        if positions:
            globe_pos = np.array(positions, dtype=np.float32)
            globe_col = np.array(colors,    dtype=np.float32)
        else:
            globe_pos = np.zeros((1, 3), dtype=np.float32)
            globe_col = np.zeros((1, 4), dtype=np.float32)

        # --- Table rows: top-_TABLE_MAX by elevation; all string/color work off main thread ---
        table_sats = sorted(sats, key=lambda s: s.elevation, reverse=True)[:self._TABLE_MAX]
        table_rows = []
        for sat in table_sats:
            hex_c = SYSTEM_COLORS.get(sat.system, '#888888')
            rv, gv, bv = _hex_to_rgb_bytes(hex_c)
            el, snr = sat.elevation, sat.snr
            if el <= 0 or snr <= 0:
                bg = (int(rv * 0.12), int(gv * 0.12), int(bv * 0.12))
                fg = (int(rv * 0.40), int(gv * 0.40), int(bv * 0.40))
            elif snr >= 35:
                bg = (int(rv * 0.28), int(gv * 0.28), int(bv * 0.28))
                fg = (rv, gv, bv)
            elif snr >= 25:
                bg = (int(rv * 0.18), int(gv * 0.18), int(bv * 0.18))
                fg = (int(rv * 0.85), int(gv * 0.85), int(bv * 0.85))
            else:
                bg = (int(rv * 0.12), int(gv * 0.12), int(bv * 0.12))
                fg = (int(rv * 0.65), int(gv * 0.65), int(bv * 0.65))
            table_rows.append((
                str(sat.prn),
                sat.system,
                f"{el:.1f}",
                f"{sat.azimuth:.1f}",
                f"{snr:.1f}",
                "Yes" if sat.used_in_fix else "No",
                bg, fg,
            ))

        # --- Sky view: throttled to _SKY_INTERVAL, visible sats pre-filtered ---
        now = time.monotonic()
        update_sky = (now - self._last_sky_update) >= self._SKY_INTERVAL
        if update_sky:
            self._last_sky_update = now
            sky_sats = [s for s in sats if s.elevation >= 0]
        else:
            sky_sats = []

        self.prepared.emit(PreparedFrame(
            gps_data=gps_data,
            globe_pos=globe_pos,
            globe_col=globe_col,
            table_rows=table_rows,
            sky_sats=sky_sats,
            update_sky=update_sky,
        ))
