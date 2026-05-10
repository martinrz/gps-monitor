from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QStatusBar, QToolBar,
    QLabel, QComboBox, QPushButton, QSplitter, QSizePolicy, QWidget,
    QDialog, QGridLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSlot
from PyQt6.QtGui import QAction, QFont

from gps.receiver import GPSReceiver
from gps.data_models import GPSData, SYSTEM_COLORS, ALL_SYSTEMS
from time_module.ntp_client import NTPClient
from gui.satellite_table import SatelliteTableWidget
from gui.sky_view import SkyViewWidget
from gui.world_map import WorldMapWidget
from gui.globe_3d import Globe3DWidget
from gui.time_display import TimeDisplayWidget
from gui.sat_hover_widget import SatHoverWidget
from gui.display_worker import DisplayWorker

try:
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

_LED_GREY   = "background:#555; border-radius:7px; min-width:14px; max-width:14px; min-height:14px; max-height:14px;"
_LED_YELLOW = "background:#e0c020; border-radius:7px; min-width:14px; max-width:14px; min-height:14px; max-height:14px;"
_LED_GREEN  = "background:#22cc44; border-radius:7px; min-width:14px; max-width:14px; min-height:14px; max-height:14px;"
_LED_RED    = "background:#cc2222; border-radius:7px; min-width:14px; max-width:14px; min-height:14px; max-height:14px;"


class MainWindow(QMainWindow):
    def __init__(self, port: str = None, simulate: bool = False, use_tle: bool = False):
        super().__init__()
        self.setWindowTitle("GPS Monitor")
        self._port = port
        self._simulate = simulate
        self._use_tle = use_tle

        self._enabled_systems = set(ALL_SYSTEMS)
        self._build_ui()
        self._build_toolbar()
        self._build_constellation_toolbar()
        self._build_menu()
        self._start_threads()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._globe = Globe3DWidget()
        self._globe.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(self._globe)

        self._sat_table = SatelliteTableWidget()
        self._dock_sat = QDockWidget("Satellites", self)
        self._dock_sat.setWidget(self._sat_table)
        self._dock_sat.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_sat)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._sky_view = SkyViewWidget()
        self._time_display = TimeDisplayWidget()
        self._sat_hover = SatHoverWidget()
        right_splitter.addWidget(self._sky_view)
        right_splitter.addWidget(self._time_display)
        right_splitter.addWidget(self._sat_hover)
        right_splitter.setSizes([320, 200, 180])

        self._dock_right = QDockWidget("Sky View / Time", self)
        self._dock_right.setWidget(right_splitter)
        self._dock_right.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock_right)

        self._world_map = WorldMapWidget()
        self._dock_map = QDockWidget("World Map", self)
        self._dock_map.setWidget(self._world_map)
        self._dock_map.setMinimumHeight(180)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._dock_map)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Initializing...")

    def _build_toolbar(self):
        tb = QToolBar("GPS Source", self)
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # Source label
        lbl = QLabel("  GPS Source: ")
        lbl.setFont(QFont("Segoe UI", 9))
        tb.addWidget(lbl)

        # Source combo: Simulation + serial ports
        self._source_combo = QComboBox()
        self._source_combo.setMinimumWidth(160)
        self._source_combo.setFont(QFont("Segoe UI", 9))
        self._populate_sources()
        # Pre-select based on startup args
        if self._use_tle:
            self._source_combo.setCurrentIndex(1)   # Live TLE
        elif self._simulate or (not self._port):
            self._source_combo.setCurrentIndex(0)   # Simulation
        else:
            idx = self._source_combo.findText(self._port)
            if idx >= 0:
                self._source_combo.setCurrentIndex(idx)
        tb.addWidget(self._source_combo)

        tb.addSeparator()

        # Refresh ports button
        btn_refresh = QPushButton("⟳  Refresh")
        btn_refresh.setToolTip("Rescan for serial ports")
        btn_refresh.setFont(QFont("Segoe UI", 9))
        btn_refresh.clicked.connect(self._refresh_sources)
        tb.addWidget(btn_refresh)

        tb.addSeparator()

        # Connect button
        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._btn_connect.setMinimumWidth(80)
        self._btn_connect.setStyleSheet(
            "QPushButton { background:#1a4a8a; color:white; border-radius:4px; padding:3px 10px; }"
            "QPushButton:hover { background:#2255aa; }"
            "QPushButton:pressed { background:#0e3060; }"
        )
        self._btn_connect.clicked.connect(self._apply_source)
        tb.addWidget(self._btn_connect)

        tb.addSeparator()

        # LED status indicator
        self._led = QLabel()
        self._led.setStyleSheet(_LED_GREY)
        self._led.setToolTip("Connection status")
        tb.addWidget(self._led)

        self._led_label = QLabel("  Not connected")
        self._led_label.setFont(QFont("Segoe UI", 9))
        tb.addWidget(self._led_label)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Protocol badge (far right)
        self._proto_label = QLabel("—")
        self._proto_label.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._proto_label.setStyleSheet("color:#22cc44; padding-right:8px;")
        tb.addWidget(self._proto_label)

        tb.addSeparator()

        # Terrain toggle button
        self._btn_terrain = QPushButton("Terrain")
        self._btn_terrain.setCheckable(True)
        self._btn_terrain.setFont(QFont("Segoe UI", 9))
        self._btn_terrain.setToolTip("Toggle terrain / satellite imagery")
        self._btn_terrain.setStyleSheet(
            "QPushButton{background:#2a3a2a;color:#88cc88;border-radius:4px;padding:3px 10px;}"
            "QPushButton:checked{background:#1e5c1e;color:#aaffaa;}"
            "QPushButton:hover{background:#3a4a3a;}"
        )
        self._btn_terrain.toggled.connect(self._on_terrain_toggled)
        tb.addWidget(self._btn_terrain)

        # Orbit rings toggle button
        self._btn_orbits = QPushButton("Orbits")
        self._btn_orbits.setCheckable(True)
        self._btn_orbits.setFont(QFont("Segoe UI", 9))
        self._btn_orbits.setToolTip("Show/hide orbital altitude rings per constellation")
        self._btn_orbits.setStyleSheet(
            "QPushButton{background:#2a2a3a;color:#8888cc;border-radius:4px;padding:3px 10px;}"
            "QPushButton:checked{background:#1e1e5c;color:#aaaaff;}"
            "QPushButton:hover{background:#3a3a5a;}"
        )
        self._btn_orbits.toggled.connect(self._on_orbits_toggled)
        tb.addWidget(self._btn_orbits)

        # Orbits-only toggle button
        self._btn_orbits_only = QPushButton("Orbits Only")
        self._btn_orbits_only.setCheckable(True)
        self._btn_orbits_only.setFont(QFont("Segoe UI", 9))
        self._btn_orbits_only.setToolTip("Show orbital rings only — hide satellite dots")
        self._btn_orbits_only.setStyleSheet(
            "QPushButton{background:#2a2a3a;color:#8888cc;border-radius:4px;padding:3px 10px;}"
            "QPushButton:checked{background:#3a1e5c;color:#cc88ff;}"
            "QPushButton:hover{background:#3a3a5a;}"
        )
        self._btn_orbits_only.toggled.connect(self._on_orbits_only_toggled)
        tb.addWidget(self._btn_orbits_only)

        # Pixel mode toggle button
        self._btn_pixels = QPushButton("Pixels")
        self._btn_pixels.setCheckable(True)
        self._btn_pixels.setFont(QFont("Segoe UI", 9))
        self._btn_pixels.setToolTip("Render satellites as bright 2-pixel squares to reduce clutter")
        self._btn_pixels.setStyleSheet(
            "QPushButton{background:#2a2a3a;color:#8888cc;border-radius:4px;padding:3px 10px;}"
            "QPushButton:checked{background:#1a1a2a;color:#ffffff;}"
            "QPushButton:hover{background:#3a3a5a;}"
        )
        self._btn_pixels.toggled.connect(self._on_pixels_toggled)
        tb.addWidget(self._btn_pixels)

    def _build_constellation_toolbar(self):
        tb = QToolBar("Constellations", self)
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        lbl = QLabel("  Systems: ")
        lbl.setFont(QFont("Segoe UI", 9))
        tb.addWidget(lbl)

        self._const_buttons = {}
        labels = {
            'GPS': 'GPS', 'GLONASS': 'GLONASS', 'GALILEO': 'Galileo',
            'BEIDOU': 'BeiDou', 'QZSS': 'QZSS', 'NAVIC': 'NavIC',
            'STARLINK': 'Starlink', 'ONEWEB': 'OneWeb',
            'IRIDIUM': 'Iridium', 'STATIONS': 'ISS/Sta',
        }
        for system, label in labels.items():
            color = SYSTEM_COLORS.get(system, '#888888')
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setMinimumWidth(72)
            btn.setStyleSheet(self._const_btn_style(color, checked=True))
            btn.toggled.connect(lambda checked, s=system, c=color: self._on_constellation_toggled(s, c, checked))
            tb.addWidget(btn)
            self._const_buttons[system] = btn

        tb.addSeparator()

        # Sat count labels — updated live
        self._count_labels = {}
        for system in labels:
            color = SYSTEM_COLORS.get(system, '#888888')
            lbl_c = QLabel("0")
            lbl_c.setFont(QFont("Courier New", 8))
            lbl_c.setStyleSheet(f"color:{color}; padding-right:4px;")
            lbl_c.setToolTip(f"{system} visible satellite count")
            self._count_labels[system] = lbl_c
            tb.addWidget(lbl_c)

        tb.addSeparator()

        btn_all = QPushButton("All")
        btn_all.setFont(QFont("Segoe UI", 9))
        btn_all.setStyleSheet("QPushButton{background:#2a2a4a;color:#ddd;border-radius:3px;padding:2px 8px;}"
                              "QPushButton:hover{background:#3a3a6a;}")
        btn_all.clicked.connect(lambda: self._set_all_constellations(True))
        tb.addWidget(btn_all)

        btn_none = QPushButton("None")
        btn_none.setFont(QFont("Segoe UI", 9))
        btn_none.setStyleSheet("QPushButton{background:#2a2a4a;color:#ddd;border-radius:3px;padding:2px 8px;}"
                               "QPushButton:hover{background:#3a3a6a;}")
        btn_none.clicked.connect(lambda: self._set_all_constellations(False))
        tb.addWidget(btn_none)

    @staticmethod
    def _const_btn_style(color: str, checked: bool) -> str:
        if checked:
            return (f"QPushButton{{background:{color};color:#000;font-weight:bold;"
                    f"border-radius:4px;padding:2px 6px;}}"
                    f"QPushButton:hover{{background:{color};opacity:0.8;}}")
        else:
            return (f"QPushButton{{background:#2a2a4a;color:{color};font-weight:bold;"
                    f"border:1px solid {color};border-radius:4px;padding:2px 6px;}}"
                    f"QPushButton:hover{{background:#3a3a6a;}}")

    def _on_constellation_toggled(self, system: str, color: str, checked: bool):
        btn = self._const_buttons[system]
        btn.setStyleSheet(self._const_btn_style(color, checked))
        if checked:
            self._enabled_systems.add(system)
        else:
            self._enabled_systems.discard(system)
        if hasattr(self, '_gps_receiver'):
            self._gps_receiver.set_constellations(self._enabled_systems)

    def _set_all_constellations(self, state: bool):
        for system, btn in self._const_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(state)
            color = SYSTEM_COLORS.get(system, '#888888')
            btn.setStyleSheet(self._const_btn_style(color, state))
            btn.blockSignals(False)
        self._enabled_systems = set(self._const_buttons.keys()) if state else set()
        if hasattr(self, '_gps_receiver'):
            self._gps_receiver.set_constellations(self._enabled_systems)

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        action_quit = QAction("Quit", self)
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def _populate_sources(self):
        self._source_combo.clear()
        self._source_combo.addItem("Simulation",              userData='sim')
        self._source_combo.addItem("Live TLE (CelesTrak)",    userData='tle')
        if SERIAL_AVAILABLE:
            for p in serial.tools.list_ports.comports():
                desc = f"{p.device}  ({p.description})" if p.description != "n/a" else p.device
                self._source_combo.addItem(desc, userData=p.device)

    def _refresh_sources(self):
        current = self._source_combo.currentData()
        self._populate_sources()
        for i in range(self._source_combo.count()):
            if self._source_combo.itemData(i) == current:
                self._source_combo.setCurrentIndex(i)
                break
        self._status_bar.showMessage("Ports refreshed.")

    def _apply_source(self):
        idx       = self._source_combo.currentIndex()
        user_data = self._source_combo.itemData(idx)

        self._stop_gps()
        self._set_led("connecting")

        if user_data == 'sim':
            self._simulate = True
            self._use_tle  = False
            self._port     = None
            self._proto_label.setText("SIM")
        elif user_data == 'tle':
            self._simulate = False
            self._use_tle  = True
            self._port     = None
            self._proto_label.setText("TLE")
        else:
            self._simulate = False
            self._use_tle  = False
            self._port     = user_data or self._source_combo.currentText().split()[0]
            self._proto_label.setText("—")

        self._start_threads()

    # ------------------------------------------------------------------
    # LED helper
    # ------------------------------------------------------------------

    def _set_led(self, state: str):
        styles = {
            "off":        (_LED_GREY,   "Not connected"),
            "connecting": (_LED_YELLOW, "Connecting…"),
            "ok":         (_LED_GREEN,  "Connected"),
            "error":      (_LED_RED,    "Error"),
        }
        style, label = styles.get(state, (_LED_GREY, ""))
        self._led.setStyleSheet(style)
        self._led_label.setText(f"  {label}")

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    def _start_threads(self):
        # Display worker — created once, persists across source switches
        if not hasattr(self, '_display_worker'):
            self._display_thread = QThread()
            self._display_worker = DisplayWorker()
            self._display_worker.moveToThread(self._display_thread)
            self._display_worker.prepared.connect(self._on_prepared)
            self._display_thread.start()

        self._gps_thread = QThread()
        self._gps_receiver = GPSReceiver(port=self._port, simulate=self._simulate,
                                         use_tle=self._use_tle)
        self._gps_receiver.moveToThread(self._gps_thread)
        self._gps_thread.started.connect(self._gps_receiver.run)
        self._gps_receiver.data_ready.connect(self._display_worker.process)
        self._gps_receiver.status_changed.connect(self._on_gps_status)
        self._gps_receiver.error_occurred.connect(self._on_gps_error)
        self._gps_thread.start()
        self._set_led("connecting")

        # Globe ↔ location signals — connect once only; source switches reuse same widgets
        if not hasattr(self, '_location_signals_connected'):
            self._globe.observer_moved.connect(self._on_observer_moved)
            self._globe.satellite_selected.connect(self._on_satellite_selected)
            self._globe.satellite_hovered.connect(self._sat_hover.show_satellite)
            self._world_map.location_clicked.connect(self._on_observer_moved)
            self._location_signals_connected = True

        # NTP thread is independent of GPS source — start once only
        if not hasattr(self, '_ntp_thread'):
            self._ntp_thread = QThread()
            self._ntp_client = NTPClient()
            self._ntp_client.moveToThread(self._ntp_thread)
            self._ntp_thread.started.connect(self._ntp_client.run)
            self._ntp_client.time_updated.connect(self._on_time_update)
            self._ntp_client.status_changed.connect(self._on_ntp_status)
            self._ntp_thread.start()

    def _stop_gps(self):
        if hasattr(self, '_gps_receiver'):
            self._gps_receiver.stop()
        if hasattr(self, '_gps_thread'):
            self._gps_thread.quit()
            if not self._gps_thread.wait(7000):
                self._park_thread(self._gps_thread)
        self._set_led("off")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot(object)
    def _on_prepared(self, frame):
        self._set_led("ok")
        data = frame.gps_data
        self._proto_label.setText(data.protocol)

        # Fast widget updates — all heavy computation already done on display thread
        self._globe.apply_prepared(frame.globe_pos, frame.globe_col, data.satellites)
        self._sat_table.apply_rows(frame.table_rows)
        if frame.update_sky:
            self._sky_view.update_satellites(frame.sky_sats)
        self._time_display.update_gps_time(data.gps_time, data.gps_date)

        if hasattr(self, '_count_labels'):
            counts = {}
            for s in data.satellites:
                if s.elevation > 0:
                    counts[s.system] = counts.get(s.system, 0) + 1
            for sys, lbl in self._count_labels.items():
                lbl.setText(str(counts.get(sys, 0)))

        if data.fix and data.fix.fix_quality > 0:
            self._world_map.update_position(data.fix.latitude, data.fix.longitude)
            sats_visible = sum(1 for s in data.satellites if s.elevation > 0)
            self._status_bar.showMessage(
                f"Protocol: {data.protocol} | Fix: {data.fix.fix_quality} | "
                f"Sats: {data.fix.num_sats_used} used, {sats_visible} visible | "
                f"Lat: {data.fix.latitude:.5f}° Lon: {data.fix.longitude:.5f}° "
                f"Alt: {data.fix.altitude:.1f}m"
            )

    @pyqtSlot(object)
    def _on_time_update(self, estimate):
        self._time_display.update_time_estimate(estimate)

    @pyqtSlot(str)
    def _on_gps_status(self, msg: str):
        self._status_bar.showMessage(f"GPS: {msg}")
        if "detected" in msg.lower() or "simulation" in msg.lower():
            self._set_led("ok")
        elif "error" in msg.lower() or "no gps" in msg.lower():
            self._set_led("error")

    @pyqtSlot(str)
    def _on_gps_error(self, msg: str):
        self._set_led("error")
        self._status_bar.showMessage(f"GPS Error: {msg}")

    @pyqtSlot(str)
    def _on_ntp_status(self, msg: str):
        pass

    @pyqtSlot(float, float)
    def _on_observer_moved(self, lat: float, lon: float):
        self._globe.set_observer(lat, lon)
        self._world_map.update_position(lat, lon)
        if hasattr(self, '_gps_receiver'):
            self._gps_receiver.set_location(lat, lon)
        self._status_bar.showMessage(
            f"Observer moved → Lat: {lat:.4f}°  Lon: {lon:.4f}°"
        )

    @pyqtSlot(object)
    def _on_satellite_selected(self, sat):
        dlg = _SatelliteDetailDialog(sat, parent=self)
        dlg.show()

    @pyqtSlot(bool)
    def _on_terrain_toggled(self, on: bool):
        self._globe.toggle_terrain()
        self._world_map.set_terrain(on)

    @pyqtSlot(bool)
    def _on_orbits_toggled(self, on: bool):
        self._globe.toggle_orbit_rings()

    @pyqtSlot(bool)
    def _on_orbits_only_toggled(self, on: bool):
        self._globe.toggle_orbits_only()
        # Keep the Orbits button in sync with ring state (block signal to avoid re-entry)
        self._btn_orbits.blockSignals(True)
        self._btn_orbits.setChecked(self._globe._rings_enabled)
        self._btn_orbits.blockSignals(False)

    @pyqtSlot(bool)
    def _on_pixels_toggled(self, on: bool):
        self._globe.toggle_pixel_mode()

    def _park_thread(self, thread):
        """Keep a Python reference to a still-running QThread so GC cannot destroy it."""
        if not hasattr(self, '_dying_threads'):
            self._dying_threads = []
        self._dying_threads.append(thread)
        thread.finished.connect(
            lambda t=thread: self._dying_threads.remove(t)
            if t in self._dying_threads else None
        )

    def closeEvent(self, event):
        self._stop_gps()
        if hasattr(self, '_display_thread'):
            self._display_thread.quit()
            self._display_thread.wait(3000)
        if hasattr(self, '_ntp_client'):
            self._ntp_client.stop()
        if hasattr(self, '_ntp_thread'):
            self._ntp_thread.quit()
            if not self._ntp_thread.wait(6000):
                self._park_thread(self._ntp_thread)
        for t in list(getattr(self, '_dying_threads', [])):
            t.wait(8000)
        super().closeEvent(event)


class _SatelliteDetailDialog(QDialog):
    def __init__(self, sat, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{sat.system}  PRN {sat.prn}")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        grid = QGridLayout(self)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnMinimumWidth(1, 160)

        def row(r, label, value, color='#dddddd'):
            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color:#888888;")
            val = QLabel(str(value))
            val.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            val.setStyleSheet(f"color:{color};")
            grid.addWidget(lbl, r, 0)
            grid.addWidget(val, r, 1)

        from gps.data_models import SYSTEM_COLORS
        sys_color = SYSTEM_COLORS.get(sat.system, '#888888')

        row(0,  "System",    sat.system,                        sys_color)
        row(1,  "PRN",       sat.prn)
        row(2,  "Elevation", f"{sat.elevation:.1f}°",
            '#22cc44' if sat.elevation > 10 else '#cc8822')
        row(3,  "Azimuth",   f"{sat.azimuth:.1f}°")
        row(4,  "SNR",       f"{sat.snr:.1f} dBHz",
            '#22cc44' if sat.snr >= 25 else '#cc4422')
        row(5,  "Latitude",  f"{sat.sat_lat:.3f}°" if sat.sat_lat  is not None else "—")
        row(6,  "Longitude", f"{sat.sat_lon:.3f}°" if sat.sat_lon  is not None else "—")
        row(7,  "Altitude",  f"{sat.altitude_km:.0f} km" if sat.altitude_km is not None else "—")
        row(8,  "In fix",    "Yes" if sat.used_in_fix else "No",
            '#22cc44' if sat.used_in_fix else '#888888')

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.close)
        grid.addWidget(btns, 9, 0, 1, 2)

        self.setStyleSheet("background:#1a1a2e; color:#dddddd;")
        self.adjustSize()
