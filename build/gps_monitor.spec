# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for GPS Monitor.
Run from the project root:
    pyinstaller build/gps_monitor.spec --clean

Produces:
  macOS : dist/GPS Monitor.app  (then wrapped in a DMG by build_mac.sh)
  Windows: dist/GPS Monitor/    (then wrapped in an installer by build_windows.bat)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH is the directory of this .spec file (i.e. build/).
# ROOT is the project root one level up.
ROOT = os.path.normpath(os.path.join(SPECPATH, '..'))

# ---------------------------------------------------------------------------
# Data files — non-Python assets that must travel with the bundle
# ---------------------------------------------------------------------------
datas = []

# VisPy GLSL shaders — required at runtime by all visual objects
datas += collect_data_files('vispy')

# Matplotlib fonts, style sheets, colormaps
datas += collect_data_files('matplotlib')

# certifi CA bundle — needed for HTTPS downloads inside the frozen app
datas += collect_data_files('certifi')

# folium Jinja2 templates (map HTML generation)
datas += collect_data_files('folium')
datas += collect_data_files('branca')      # folium dependency (colour names, templates)

# cartopy Natural Earth data and projection definitions
datas += collect_data_files('cartopy')

# sgp4 data files (Earth orientation parameters etc.)
datas += collect_data_files('sgp4')

# ---------------------------------------------------------------------------
# Hidden imports — modules PyInstaller cannot detect through static analysis
# ---------------------------------------------------------------------------
hiddenimports = [
    # VisPy backend selector — must match vispy.use('PyQt6') in globe_3d.py
    'vispy.app.backends._pyqt6',
    'vispy.glsl',

    # PyQt6 WebEngine (used by WorldMapWidget)
    'PyQt6.QtWebEngineWidgets',
    'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebChannel',
    'PyQt6.QtWebSockets',

    # matplotlib Qt backend (used by SkyViewWidget and WorldMapWidget fallback)
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_agg',

    # Our local protocol parsers (in a sub-package, sometimes missed)
    'gps.protocols.nmea',
    'gps.protocols.ubx',
    'gps.protocols.sirf',

    # SGP4 propagator
    'sgp4',
    'sgp4.api',
    'sgp4.model',
    'sgp4.earth_gravity',

    # Serial port enumeration
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
    'serial.tools.list_ports_posix',   # macOS/Linux
    'serial.tools.list_ports_windows', # Windows

    # NMEA / UBX parsers
    'pynmea2',
    'pyubx2',

    # NTP
    'ntplib',

    # cartopy internals used at runtime
    'cartopy',
    'cartopy.crs',
    'cartopy.feature',
    'cartopy.io',
    'cartopy.io.shapereader',
    'cartopy.mpl',
    'cartopy.mpl.geoaxes',
    'cartopy.mpl.feature_artist',

    # shapely (cartopy dependency)
    'shapely',
    'shapely.geometry',
    'shapely.ops',

    # folium internals
    'folium',
    'jinja2',
    'jinja2.ext',

    # numpy / scipy sub-modules sometimes missed
    'numpy',
    'numpy.core._multiarray_umath',
]

# ---------------------------------------------------------------------------
# Exclusions — reduce bundle size by dropping things we don't use
# ---------------------------------------------------------------------------
excludes = [
    'tkinter',
    '_tkinter',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'sphinx',
    'wx',
    'gi',
    'gtk',
]

# ---------------------------------------------------------------------------
# Icon paths
# ---------------------------------------------------------------------------
ICON_ICNS = os.path.join(SPECPATH, 'icons', 'icon.icns')
ICON_ICO  = os.path.join(SPECPATH, 'icons', 'icon.ico')

icon_file = ICON_ICNS if sys.platform == 'darwin' else ICON_ICO
if not os.path.exists(icon_file):
    icon_file = None   # fall back to no icon if not generated yet

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(SPECPATH, 'hooks')],
    hooksconfig={},
    runtime_hooks=[os.path.join(SPECPATH, 'runtime_hook.py')],
    excludes=excludes,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Package — PYZ archive of all Python modules
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Executable
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],                  # no single-file embedding; use COLLECT below
    exclude_binaries=True,
    name='GPS Monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX can break Qt binaries; keep off
    console=False,       # no terminal window
    icon=icon_file,
    codesign_identity=None,
    entitlements_file=None,
)

# ---------------------------------------------------------------------------
# Collect — assemble the one-directory bundle
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GPS Monitor',
)

# ---------------------------------------------------------------------------
# macOS .app bundle
# ---------------------------------------------------------------------------
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='GPS Monitor.app',
        icon=icon_file,
        bundle_identifier='com.martinreynolds.gpsmonitor',
        version='1.0.0',
        info_plist={
            'CFBundleName':               'GPS Monitor',
            'CFBundleDisplayName':        'GPS Monitor',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion':            '1.0.0',
            'NSHighResolutionCapable':    True,
            'NSRequiresAquaSystemAppearance': False,   # supports dark mode
            'LSMinimumSystemVersion':     '12.0',
            'NSPrincipalClass':           'NSApplication',
            'NSAppleScriptEnabled':       False,
        },
    )
