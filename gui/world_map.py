import time
from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

try:
    import folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Matplotlib fallback
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np

_TILES_DARK    = 'CartoDB dark_matter'
_TILES_TERRAIN = ('https://server.arcgisonline.com/ArcGIS/rest/services/'
                  'World_Imagery/MapServer/tile/{z}/{y}/{x}')
_TILES_TERRAIN_ATTR = 'Tiles &copy; Esri'

_CLICK_JS = """
(function() {
    var poll = setInterval(function() {
        try {
            var maps = [];
            for (var k in window) {
                try { if (window[k] && window[k] instanceof L.Map) maps.push(window[k]); }
                catch(e) {}
            }
            if (maps.length) {
                clearInterval(poll);
                maps[0].on('click', function(e) {
                    var lat = e.latlng.lat.toFixed(6);
                    var lon = e.latlng.lng.toFixed(6);
                    document.title = 'GPS_CLICK:' + lat + ':' + lon;
                });
            }
        } catch(e) {}
    }, 300);
})();
"""


class WorldMapWidget(QWidget):
    THROTTLE_S = 2.0

    location_clicked = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._last_update = 0.0
        self._lat: Optional[float] = None
        self._lon: Optional[float] = None
        self._terrain = False

        if WEBENGINE_AVAILABLE and FOLIUM_AVAILABLE:
            self._web = QWebEngineView()
            self._web.titleChanged.connect(self._on_title_changed)
            self._web.loadFinished.connect(self._inject_click_handler)
            layout.addWidget(self._web)
            self._mode = 'folium'
            self._show_initial_map()
        else:
            self._fig = Figure(figsize=(6, 3), facecolor='#1a1a2e')
            self._ax = self._fig.add_subplot(111)
            self._canvas_mpl = FigureCanvasQTAgg(self._fig)
            self._canvas_mpl.mpl_connect('button_press_event', self._on_mpl_click)
            layout.addWidget(self._canvas_mpl)
            self._mode = 'matplotlib'
            self._setup_mpl_map()

    # ------------------------------------------------------------------
    # Folium helpers
    # ------------------------------------------------------------------

    def _show_initial_map(self):
        m = self._make_folium_map(20.0, 0.0, zoom=2)
        self._web.setHtml(m._repr_html_())

    def _make_folium_map(self, lat, lon, zoom=6):
        if self._terrain:
            m = folium.Map(location=[lat, lon], zoom_start=zoom,
                           tiles=_TILES_TERRAIN, attr=_TILES_TERRAIN_ATTR)
        else:
            m = folium.Map(location=[lat, lon], zoom_start=zoom,
                           tiles=_TILES_DARK)
        return m

    def _inject_click_handler(self, ok=True):
        if self._mode == 'folium' and ok:
            self._web.page().runJavaScript(_CLICK_JS)

    def _on_title_changed(self, title: str):
        if title.startswith('GPS_CLICK:'):
            parts = title.split(':')
            try:
                lat, lon = float(parts[1]), float(parts[2])
                self.location_clicked.emit(lat, lon)
            except (IndexError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Matplotlib helpers
    # ------------------------------------------------------------------

    def _setup_mpl_map(self):
        ax = self._ax
        ax.set_facecolor('#1a1a2e')
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_aspect('equal')
        ax.grid(color='#334466', linewidth=0.3)
        ax.set_xlabel('Longitude', color='#aaaaaa', fontsize=8)
        ax.set_ylabel('Latitude',  color='#aaaaaa', fontsize=8)
        ax.tick_params(colors='#aaaaaa', labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor('#334466')
        self._fig.tight_layout(pad=0.5)
        self._mpl_marker = None

    def _on_mpl_click(self, event):
        if event.xdata is not None and event.ydata is not None:
            self.location_clicked.emit(float(event.ydata), float(event.xdata))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_terrain(self, enabled: bool):
        self._terrain = enabled
        if self._mode == 'folium':
            if self._lat is not None:
                self._update_folium(self._lat, self._lon)
            else:
                self._show_initial_map()

    def update_position(self, lat: float, lon: float):
        self._lat = lat
        self._lon = lon
        now = time.time()
        if now - self._last_update < self.THROTTLE_S:
            return
        self._last_update = now

        if self._mode == 'folium':
            self._update_folium(lat, lon)
        else:
            self._update_mpl(lat, lon)

    def _update_folium(self, lat: float, lon: float):
        m = self._make_folium_map(lat, lon, zoom=6)
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,
            color='#22cc44',
            fill=True,
            fill_color='#22cc44',
            fill_opacity=0.8,
            popup=f"Observer<br>Lat: {lat:.5f}<br>Lon: {lon:.5f}"
        ).add_to(m)
        self._web.setHtml(m._repr_html_())

    def _update_mpl(self, lat: float, lon: float):
        ax = self._ax
        if self._mpl_marker:
            try:
                self._mpl_marker.remove()
            except ValueError:
                pass
        self._mpl_marker = ax.scatter([lon], [lat], c='#22cc44', s=80, zorder=5)
        self._canvas_mpl.draw_idle()
