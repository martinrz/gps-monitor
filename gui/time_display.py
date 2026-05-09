import time
from typing import Optional
from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from gps.data_models import TimeEstimate


class TimeDisplayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setSpacing(6)

        mono = QFont("Courier New", 10)
        large_mono = QFont("Courier New", 14)
        large_mono.setBold(True)

        self._utc_label = QLabel("--:--:-- UTC")
        self._utc_label.setFont(large_mono)
        self._utc_label.setStyleSheet("color: #22cc44;")

        self._gps_label = QLabel("--:--:--")
        self._gps_label.setFont(large_mono)
        self._gps_label.setStyleSheet("color: #4488ff;")

        self._ntp_label = QLabel("Waiting for NTP...")
        self._ntp_label.setFont(mono)
        self._ntp_label.setStyleSheet("color: #cccccc;")

        self._ntp_uncertainty = QLabel("--")
        self._ntp_uncertainty.setFont(mono)
        self._ntp_uncertainty.setStyleSheet("color: #aaaaaa;")

        self._ntp_servers = QLabel("0")
        self._ntp_servers.setFont(mono)
        self._ntp_servers.setStyleSheet("color: #aaaaaa;")

        self._gps_ntp_offset = QLabel("--")
        self._gps_ntp_offset.setFont(mono)
        self._gps_ntp_offset.setStyleSheet("color: #ffaa22;")

        self._gps_date = QLabel("--/--/----")
        self._gps_date.setFont(mono)
        self._gps_date.setStyleSheet("color: #aaaaaa;")

        layout.addRow("System UTC:", self._utc_label)
        layout.addRow("GPS Time:", self._gps_label)
        layout.addRow("GPS Date:", self._gps_date)
        layout.addRow("NTP Time:", self._ntp_label)
        layout.addRow("NTP Uncertainty:", self._ntp_uncertainty)
        layout.addRow("NTP Servers:", self._ntp_servers)
        layout.addRow("GPS-NTP Offset:", self._gps_ntp_offset)

        self._gps_time_str: Optional[str] = None
        self._time_estimate: Optional[TimeEstimate] = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)

    def update_gps_time(self, gps_time: Optional[str], gps_date: Optional[str]):
        self._gps_time_str = gps_time
        if gps_date:
            self._gps_date.setText(gps_date)

    def update_time_estimate(self, estimate: TimeEstimate):
        self._time_estimate = estimate

    def _tick(self):
        # System UTC (always live)
        t = time.gmtime()
        self._utc_label.setText(f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d} UTC")

        # GPS time from last received sentence
        if self._gps_time_str:
            self._gps_label.setText(self._gps_time_str)

        # NTP estimate
        if self._time_estimate:
            est = self._time_estimate
            t_ntp = time.gmtime(est.utc_time)
            self._ntp_label.setText(
                f"{t_ntp.tm_hour:02d}:{t_ntp.tm_min:02d}:{t_ntp.tm_sec:02d} UTC"
            )
            self._ntp_uncertainty.setText(f"±{est.uncertainty_ms:.3f} ms")
            self._ntp_servers.setText(str(est.contributing_servers))
            if est.gps_offset_ms is not None:
                self._gps_ntp_offset.setText(f"{est.gps_offset_ms:+.1f} ms")
            else:
                self._gps_ntp_offset.setText("--")
