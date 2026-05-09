import sys
import os
import ssl
import argparse
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Fix macOS Python SSL certificate issue — system certs not trusted by default.
# Patch the default HTTPS context to use certifi's bundle so all downloads
# (TLE data, cartopy Natural Earth shapefiles, NTP, etc.) work without errors.
try:
    import certifi
    ssl._create_default_https_context = lambda: ssl.create_default_context(
        cafile=certifi.where()
    )
except Exception:
    pass

# Suppress "SetProcessDpiAwarenessContext() failed: Access is denied" —
# the context is already set correctly by the host process; Qt just can't
# re-set it, but DPI awareness is working fine.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")


def main():
    from utils.log_config import setup as _log_setup
    _log_setup()
    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="GPS Monitor Application")
    parser.add_argument('--simulate', action='store_true',
                        help='Run in simulation mode (no hardware required)')
    parser.add_argument('--tle', action='store_true',
                        help='Start in Live TLE mode (downloads data from CelesTrak)')
    parser.add_argument('--port', type=str, default=None,
                        help='Serial port for GPS receiver (e.g. COM3 or /dev/ttyUSB0)')
    args = parser.parse_args()
    mode = 'TLE' if args.tle else ('simulation' if args.simulate else f'serial:{args.port}')
    log.info("Starting GPS Monitor — mode: %s", mode)

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Dark palette
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(26, 26, 46))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base, QColor(18, 18, 36))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 30, 54))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(40, 40, 70))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button, QColor(40, 40, 70))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(34, 100, 200))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    from gui.main_window import MainWindow
    from PyQt6.QtCore import QTimer

    window = MainWindow(port=args.port, simulate=args.simulate, use_tle=args.tle)

    # Size the window to 90% of available screen, then enforce dock widths
    screen = app.primaryScreen().availableGeometry()
    w = int(screen.width() * 0.92)
    h = int(screen.height() * 0.92)
    window.resize(w, h)
    window.move(screen.x() + (screen.width() - w) // 2,
                screen.y() + (screen.height() - h) // 2)
    window.show()

    def _resize_docks():
        sat_w  = max(300, w // 6)
        right_w = max(320, w // 5)
        map_h  = max(200, h // 4)
        window.resizeDocks(
            [window._dock_sat, window._dock_right],
            [sat_w, right_w],
            Qt.Orientation.Horizontal
        )
        window.resizeDocks([window._dock_map], [map_h], Qt.Orientation.Vertical)

    QTimer.singleShot(300, _resize_docks)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
