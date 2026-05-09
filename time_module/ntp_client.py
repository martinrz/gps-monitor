import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from gps.data_models import NTPResult, TimeEstimate

log = logging.getLogger(__name__)

try:
    import ntplib
    NTP_AVAILABLE = True
except ImportError:
    NTP_AVAILABLE = False

NTP_SERVERS = [
    'pool.ntp.org',
    'time.google.com',
    'time.cloudflare.com',
    'time.windows.com',
    'ntp.ubuntu.com',
    'time1.google.com',
    'time2.google.com',
    'time3.google.com',
]
QUERY_INTERVAL = 30.0   # seconds between NTP updates


class NTPClient(QObject):
    time_updated = pyqtSignal(object)   # TimeEstimate
    status_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running = False
        self._last_gps_time: Optional[float] = None
        self._last_gps_ts: Optional[float] = None

    def set_gps_time(self, gps_unix: float):
        self._last_gps_time = gps_unix
        self._last_gps_ts = time.time()

    @pyqtSlot()
    def run(self):
        try:
            self._running = True
            while self._running:
                try:
                    estimate = self._query()
                    if estimate:
                        self.time_updated.emit(estimate)
                except Exception as exc:
                    log.warning("NTP query cycle failed: %s", exc)
                for _ in range(int(QUERY_INTERVAL * 10)):
                    if not self._running:
                        break
                    time.sleep(0.1)
        except Exception as exc:
            log.exception("NTPClient.run() fatal: %s", exc)

    def stop(self):
        self._running = False

    def _query_server(self, server: str) -> NTPResult:
        if not NTP_AVAILABLE:
            return NTPResult(server=server, offset=0.0, delay=0.1,
                             stratum=2, success=False, error="ntplib not available")
        try:
            c = ntplib.NTPClient()
            resp = c.request(server, version=3, timeout=3)
            return NTPResult(
                server=server,
                offset=resp.offset,
                delay=resp.delay,
                stratum=resp.stratum,
                success=True
            )
        except Exception as e:
            return NTPResult(server=server, offset=0.0, delay=999.0,
                             stratum=99, success=False, error=str(e))

    def _query(self) -> Optional[TimeEstimate]:
        self.status_changed.emit("Querying NTP servers...")
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self._query_server, s): s for s in NTP_SERVERS}
            try:
                for future in as_completed(futures, timeout=5.0):
                    try:
                        results.append(future.result())
                    except Exception:
                        pass
            except Exception:
                pass  # TimeoutError if servers didn't all respond in 5s; use whatever arrived

        good = [r for r in results if r.success and r.delay < 10.0]
        if not good:
            self.status_changed.emit("NTP: no servers responded")
            return None

        offsets = np.array([r.offset for r in good])
        delays = np.array([r.delay for r in good])

        # Outlier rejection: |offset - median| > 2σ
        if len(offsets) > 2:
            median = np.median(offsets)
            sigma = np.std(offsets)
            mask = np.abs(offsets - median) <= 2 * sigma
            if mask.sum() >= 2:
                offsets = offsets[mask]
                delays = delays[mask]
                good = [r for r, m in zip(good, mask) if m]

        # Weighted average: weight = 1/delay^2
        weights = 1.0 / (delays ** 2)
        weights /= weights.sum()
        weighted_offset = np.dot(weights, offsets)

        # Weighted standard deviation (uncertainty), floor at 1 μs
        variance = np.dot(weights, (offsets - weighted_offset) ** 2)
        uncertainty_ms = max(np.sqrt(variance) * 1000.0, 0.001)

        ntp_utc = time.time() + weighted_offset

        # GPS-NTP offset
        gps_offset_ms = None
        if self._last_gps_time and self._last_gps_ts:
            elapsed = time.time() - self._last_gps_ts
            projected_gps = self._last_gps_time + elapsed
            gps_offset_ms = (projected_gps - ntp_utc) * 1000.0

        self.status_changed.emit(
            f"NTP: {len(good)} servers, ±{uncertainty_ms:.2f}ms"
        )
        return TimeEstimate(
            utc_time=ntp_utc,
            uncertainty_ms=uncertainty_ms,
            contributing_servers=len(good),
            gps_offset_ms=gps_offset_ms,
            method="NTP"
        )
