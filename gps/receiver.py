import time
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from gps.data_models import GPSData

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from gps.protocols.nmea import NMEAParser
from gps.protocols.ubx import UBXParser
from gps.protocols.sirf import SiRFParser
from gps.simulator import GPSSimulator
from gps.tle_simulator import TLESimulator, TLE_SYSTEMS

BAUD_RATES = [9600, 4800, 38400, 115200]
DETECT_TIMEOUT = 3.0    # seconds to attempt detection per baud rate


class GPSReceiver(QObject):
    data_ready = pyqtSignal(object)         # GPSData
    status_changed = pyqtSignal(str)        # status string
    error_occurred = pyqtSignal(str)        # error message

    def __init__(self, port: str = None, simulate: bool = False, use_tle: bool = False):
        super().__init__()
        self._port = port
        self._simulate = simulate
        self._use_tle = use_tle
        self._running = False
        self._serial = None
        self._protocol = None
        self._protocol_name = "UNKNOWN"
        self._simulator = None
        self._tle_sim = None
        from gps.data_models import ALL_SYSTEMS
        self._enabled_systems = set(ALL_SYSTEMS)

    @pyqtSlot(object)
    def set_constellations(self, systems):
        self._enabled_systems = set(systems)
        if self._simulator:
            self._simulator.set_enabled_systems(self._enabled_systems)
        if self._tle_sim:
            self._tle_sim.set_enabled_systems(self._enabled_systems)

    @pyqtSlot(float, float)
    def set_location(self, lat: float, lon: float):
        if self._simulator:
            self._simulator.set_location(lat, lon)
        if self._tle_sim:
            self._tle_sim.set_location(lat, lon)

    @pyqtSlot()
    def run(self):
        self._running = True
        if self._use_tle:
            self._run_tle_mode()
            return
        if self._simulate or not SERIAL_AVAILABLE:
            self._run_simulation()
            return
        if self._port:
            self._connect_to_port(self._port)
        else:
            self._auto_detect()

    def stop(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()

    def _run_simulation(self):
        self.status_changed.emit("Simulation mode active")
        self._simulator = GPSSimulator()
        self._simulator.set_enabled_systems(self._enabled_systems)
        while self._running:
            data = self._simulator.get_gps_data()
            self.data_ready.emit(data)
            time.sleep(1.0)

    def _run_tle_mode(self):
        self.status_changed.emit("TLE mode: downloading satellite data from CelesTrak…")
        self._tle_sim = TLESimulator()
        self._tle_sim.set_enabled_systems(self._enabled_systems)
        self._tle_sim.preload(stop_check=lambda: not self._running)
        if not self._running:
            return
        self.status_changed.emit("TLE mode active")
        while self._running:
            data = self._tle_sim.get_gps_data()
            self.data_ready.emit(data)
            time.sleep(1.0)

    def _auto_detect(self):
        if not SERIAL_AVAILABLE:
            self._run_simulation()
            return

        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            self.status_changed.emit("No serial ports found — falling back to simulation")
            self._run_simulation()
            return

        for port in ports:
            for baud in BAUD_RATES:
                if not self._running:
                    return
                self.status_changed.emit(f"Trying {port} @ {baud}...")
                detected = self._try_port(port, baud)
                if detected:
                    return

        self.status_changed.emit("No GPS device detected — falling back to simulation")
        self._run_simulation()

    def _connect_to_port(self, port: str):
        for baud in BAUD_RATES:
            if not self._running:
                return
            detected = self._try_port(port, baud)
            if detected:
                return
        self.error_occurred.emit(f"Could not detect GPS protocol on {port}")
        self._run_simulation()

    def _try_port(self, port: str, baud: int) -> bool:
        try:
            ser = serial.Serial(port, baud, timeout=1)
            deadline = time.time() + DETECT_TIMEOUT
            buf = bytearray()

            while time.time() < deadline:
                raw = ser.read(256)
                if not raw:
                    continue
                buf.extend(raw)

                if b'$GP' in buf or b'$GN' in buf or b'$GL' in buf:
                    self._serial = ser
                    self._protocol = NMEAParser()
                    self._protocol_name = "NMEA"
                    self.status_changed.emit(f"NMEA detected on {port} @ {baud}")
                    self._read_loop_nmea()
                    return True

                if b'\xB5\x62' in buf:
                    self._serial = ser
                    self._protocol = UBXParser()
                    self._protocol_name = "UBX"
                    self.status_changed.emit(f"UBX detected on {port} @ {baud}")
                    self._read_loop_ubx()
                    return True

                if b'\xA0\xA2' in buf:
                    self._serial = ser
                    self._protocol = SiRFParser()
                    self._protocol_name = "SiRF"
                    self.status_changed.emit(f"SiRF detected on {port} @ {baud}")
                    self._read_loop_sirf()
                    return True

            ser.close()
            return False
        except (OSError, serial.SerialException) as e:
            return False

    def _read_loop_nmea(self):
        parser = self._protocol
        while self._running:
            try:
                line = self._serial.readline().decode('ascii', errors='replace')
                if line:
                    data = parser.feed(line)
                    if data:
                        self.data_ready.emit(data)
            except Exception as e:
                self.error_occurred.emit(str(e))
                break

    def _read_loop_ubx(self):
        parser = self._protocol
        while self._running:
            try:
                raw = self._serial.read(1024)
                if raw:
                    data = parser.feed_bytes(raw)
                    if data:
                        self.data_ready.emit(data)
            except Exception as e:
                self.error_occurred.emit(str(e))
                break

    def _read_loop_sirf(self):
        parser = self._protocol
        while self._running:
            try:
                raw = self._serial.read(256)
                if raw:
                    results = parser.feed_bytes(raw)
                    for data in results:
                        self.data_ready.emit(data)
            except Exception as e:
                self.error_occurred.emit(str(e))
                break
