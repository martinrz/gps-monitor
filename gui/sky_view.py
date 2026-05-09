import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from gps.data_models import SYSTEM_COLORS


class SkyViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fig = Figure(figsize=(4, 4), facecolor='#1a1a2e')
        self._ax = self._fig.add_subplot(111, projection='polar')
        self._canvas = FigureCanvasQTAgg(self._fig)
        toolbar = NavigationToolbar2QT(self._canvas, self)

        layout.addWidget(toolbar)
        layout.addWidget(self._canvas)

        self._setup_axes()

    def _setup_axes(self):
        ax = self._ax
        ax.set_facecolor('#1a1a2e')
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)          # clockwise (compass)
        ax.set_rlim(0, 90)
        ax.set_yticks([0, 30, 60, 90])
        ax.set_yticklabels(['', '60°', '30°', '0°'], color='#aaaaaa', size=7)
        ax.set_xticks(np.radians([0, 45, 90, 135, 180, 225, 270, 315]))
        ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
                           color='#cccccc', size=8)
        ax.grid(color='#334466', linewidth=0.5)
        ax.tick_params(colors='#aaaaaa')
        self._fig.tight_layout(pad=0.5)

    def update_satellites(self, satellites: list):
        ax = self._ax
        ax.cla()
        self._setup_axes()

        for sat in satellites:
            if sat.elevation < 0:
                continue
            r = 90.0 - sat.elevation       # zenith = 0, horizon = 90
            theta = np.radians(sat.azimuth)

            color = SYSTEM_COLORS.get(sat.system, '#888888')
            # Dim the dot if SNR is weak
            alpha = 1.0 if sat.snr >= 25 else 0.55

            size = max(40, sat.snr * 2.5)
            ax.scatter(theta, r, s=size, c=color, alpha=alpha, zorder=5)
            ax.annotate(str(sat.prn), (theta, r),
                        textcoords='offset points', xytext=(3, 3),
                        color='white', fontsize=5, zorder=6)

        self._canvas.draw_idle()
