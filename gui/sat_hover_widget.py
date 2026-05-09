"""Compact satellite info panel shown in the right pane on globe hover."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from gps.data_models import SYSTEM_COLORS


class SatHoverWidget(QWidget):
    """Shows key fields for the satellite currently hovered on the globe.

    Call show_satellite(sat) with a SatelliteInfo or None to update.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(40)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(3)

        # Name line — prominent, colored by system
        self._name_label = QLabel("— hover over a satellite —")
        self._name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._name_label.setStyleSheet("color:#555566;")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        outer.addWidget(self._name_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2a2a4a;")
        outer.addWidget(sep)

        # Detail grid — hidden when no satellite
        self._detail = QWidget()
        grid = QGridLayout(self._detail)
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        grid.setColumnMinimumWidth(0, 64)
        grid.setColumnMinimumWidth(2, 64)

        self._vals = {}
        # Two-column layout: left col (label+val), right col (label+val)
        fields = [
            # (key, display_label, row, col_offset)
            ('system',   'System',   0, 0),
            ('prn',      'PRN',      0, 2),
            ('elevation','Elevation',1, 0),
            ('azimuth',  'Azimuth',  1, 2),
            ('snr',      'SNR',      2, 0),
            ('infix',    'In fix',   2, 2),
            ('position', 'Sub-sat',  3, 0),
            ('altitude', 'Altitude', 3, 2),
        ]
        for key, display, row, col in fields:
            lbl = QLabel(display)
            lbl.setFont(QFont("Segoe UI", 8))
            lbl.setStyleSheet("color:#555566;")
            val = QLabel("—")
            val.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            val.setStyleSheet("color:#aaaaaa;")
            grid.addWidget(lbl, row, col)
            grid.addWidget(val, row, col + 1)
            self._vals[key] = val

        outer.addWidget(self._detail)
        outer.addStretch()

        self._detail.setVisible(False)
        self.setStyleSheet(
            "SatHoverWidget { background:#0e0e1c; border-top: 1px solid #1e1e3a; }"
        )

    def show_satellite(self, sat):
        if sat is None:
            self._name_label.setText("— hover over a satellite —")
            self._name_label.setStyleSheet("color:#555566;")
            self._detail.setVisible(False)
            return

        color = SYSTEM_COLORS.get(sat.system, '#888888')
        name = sat.name.strip() if sat.name else f"{sat.system} PRN {sat.prn}"

        self._name_label.setText(name)
        self._name_label.setStyleSheet(f"color:{color};")

        snr_color = ('#22cc44' if sat.snr >= 35
                     else '#ccaa22' if sat.snr >= 25
                     else '#cc6622' if sat.snr > 0
                     else '#666666')
        el_color = ('#22cc44' if sat.elevation > 10
                    else '#ccaa22' if sat.elevation > 0
                    else '#666666')

        self._vals['system'].setText(sat.system)
        self._vals['system'].setStyleSheet(f"color:{color}; font-weight:bold;")

        self._vals['prn'].setText(str(sat.prn))
        self._vals['prn'].setStyleSheet("color:#cccccc;")

        self._vals['elevation'].setText(f"{sat.elevation:.1f}°")
        self._vals['elevation'].setStyleSheet(f"color:{el_color};")

        self._vals['azimuth'].setText(f"{sat.azimuth:.1f}°")
        self._vals['azimuth'].setStyleSheet("color:#aaaaaa;")

        self._vals['snr'].setText(f"{sat.snr:.1f} dBHz" if sat.snr > 0 else "—")
        self._vals['snr'].setStyleSheet(f"color:{snr_color};")

        fix_color = '#22cc44' if sat.used_in_fix else '#666666'
        self._vals['infix'].setText("Yes" if sat.used_in_fix else "No")
        self._vals['infix'].setStyleSheet(f"color:{fix_color};")

        if sat.sat_lat is not None and sat.sat_lon is not None:
            self._vals['position'].setText(f"{sat.sat_lat:.2f}°  {sat.sat_lon:.2f}°")
        else:
            self._vals['position'].setText("—")
        self._vals['position'].setStyleSheet("color:#aaaaaa;")

        if sat.altitude_km is not None:
            alt_str = f"{sat.altitude_km:,.0f} km"
            self._vals['altitude'].setText(alt_str)
        else:
            self._vals['altitude'].setText("—")
        self._vals['altitude'].setStyleSheet("color:#aaaaaa;")

        self._detail.setVisible(True)
