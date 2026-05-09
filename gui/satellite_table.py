from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from gps.data_models import SYSTEM_COLORS


class SatelliteTableWidget(QTableWidget):
    COLUMNS = ['PRN', 'System', 'El°', 'Az°', 'SNR (dBHz)', 'Used']

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLUMNS), parent)
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        mono = QFont("Courier New", 9)
        self.setFont(mono)
        self.setMinimumWidth(340)

    def apply_rows(self, rows: list):
        """Fast path: apply pre-computed (prn, system, el, az, snr, used, bg_rgb, fg_rgb) tuples."""
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, (prn, system, el, az, snr, used, bg, fg) in enumerate(rows):
            bg_c, fg_c = QColor(*bg), QColor(*fg)
            for c, text in enumerate((prn, system, el, az, snr, used)):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QBrush(bg_c))
                item.setForeground(QBrush(fg_c))
                self.setItem(r, c, item)
        self.setSortingEnabled(True)

    def update_satellites(self, satellites: list):
        self.setSortingEnabled(False)
        self.setRowCount(len(satellites))

        for row, sat in enumerate(satellites):
            self._set_item(row, 0, str(sat.prn))
            self._set_item(row, 1, sat.system)
            self._set_item(row, 2, f"{sat.elevation:.1f}")
            self._set_item(row, 3, f"{sat.azimuth:.1f}")
            self._set_item(row, 4, f"{sat.snr:.1f}")
            self._set_item(row, 5, "Yes" if sat.used_in_fix else "No")

            bg, fg = self._row_colors(sat.system, sat.snr, sat.elevation)
            for col in range(len(self.COLUMNS)):
                item = self.item(row, col)
                if item:
                    item.setBackground(QBrush(bg))
                    item.setForeground(QBrush(fg))

        self.setSortingEnabled(True)

    def _set_item(self, row: int, col: int, text: str):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, col, item)

    @staticmethod
    def _row_colors(system: str, snr: float, elevation: float):
        hex_c = SYSTEM_COLORS.get(system, '#888888')
        h = hex_c.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if elevation <= 0 or snr <= 0:
            # Below horizon — very dim background, muted text
            bg = QColor(int(r * 0.12), int(g * 0.12), int(b * 0.12))
            fg = QColor(int(r * 0.4), int(g * 0.4), int(b * 0.4))
        elif snr >= 35:
            # Strong signal — vivid background
            bg = QColor(int(r * 0.28), int(g * 0.28), int(b * 0.28))
            fg = QColor(r, g, b)
        elif snr >= 25:
            # Moderate — slightly dimmer
            bg = QColor(int(r * 0.18), int(g * 0.18), int(b * 0.18))
            fg = QColor(int(r * 0.85), int(g * 0.85), int(b * 0.85))
        else:
            # Weak signal — faint
            bg = QColor(int(r * 0.12), int(g * 0.12), int(b * 0.12))
            fg = QColor(int(r * 0.65), int(g * 0.65), int(b * 0.65))
        return bg, fg
