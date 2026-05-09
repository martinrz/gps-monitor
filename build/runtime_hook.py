"""PyInstaller runtime hook — runs before any app code inside the frozen bundle.

Patches the SSL context to use certifi's bundled CA certificates so that
HTTPS downloads (TLE data, cartopy shapefiles) work correctly from inside
the frozen .app or .exe where the system certificate store is not accessible.

Also sets QT_PLUGIN_PATH so PyQt6 can locate its platform plugins when
the bundle is unpacked to a non-standard location.
"""
import os
import sys


def _patch_ssl():
    try:
        import ssl
        import certifi
        # Override the default HTTPS context factory globally.
        ssl._create_default_https_context = lambda: ssl.create_default_context(
            cafile=certifi.where()
        )
        # Also set environment variable for libraries that bypass the Python ssl module.
        os.environ.setdefault('SSL_CERT_FILE', certifi.where())
        os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())
    except Exception:
        pass


def _patch_qt_paths():
    # When running as a frozen bundle, help PyQt6 find its Qt plugin directory.
    if hasattr(sys, '_MEIPASS'):
        qt_plugins = os.path.join(sys._MEIPASS, 'PyQt6', 'Qt6', 'plugins')
        if os.path.isdir(qt_plugins):
            os.environ.setdefault('QT_PLUGIN_PATH', qt_plugins)


_patch_ssl()
_patch_qt_paths()
