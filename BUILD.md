# Building GPS Monitor Redistributables

GPS Monitor is packaged with [PyInstaller](https://pyinstaller.org/) into a self-contained
bundle that requires no Python installation on the target machine.

---

## Quick Start

### macOS

```bash
# Install build tools (one-time)
pip install pyinstaller Pillow
brew install create-dmg     # optional — gives a prettier DMG with drag-to-install layout

# Build
bash build/build_mac.sh
```

Output:
- `dist/GPS Monitor.app` — standalone macOS app bundle
- `dist/GPS_Monitor_1.0_macOS.dmg` — distributable disk image

### Windows

Run on a Windows machine with Python installed:

```bat
REM Install build tools (one-time)
pip install pyinstaller Pillow

REM Install Inno Setup 6 from https://jrsoftware.org/isinfo.php  (optional)

REM Build
build\build_windows.bat
```

Output:
- `dist\GPS Monitor\` — standalone directory bundle
- `dist\GPS_Monitor_1.0_Setup.exe` — installer (if Inno Setup is present)

---

## Build System Files

```
build/
├── gps_monitor.spec      PyInstaller specification (cross-platform)
├── build_mac.sh          macOS build script (PyInstaller → .app → .dmg)
├── build_windows.bat     Windows build script (PyInstaller → Inno Setup)
├── installer.iss         Inno Setup 6 configuration
├── runtime_hook.py       Runs inside the bundle at startup (SSL, Qt plugin paths)
├── entitlements.plist    macOS code-signing entitlements (network, serial port)
├── hooks/
│   └── hook-vispy.py     Custom hook ensuring VisPy shaders and backend are bundled
├── icons/
│   ├── make_icons.py     Generates icon.icns and icon.ico from scratch (needs Pillow)
│   ├── icon.icns         macOS icon (auto-generated)
│   ├── icon.ico          Windows icon (auto-generated)
│   └── icon.png          256×256 PNG reference
```

---

## How It Works

### PyInstaller

PyInstaller analyses `main.py`, follows all imports, and packs everything — Python
interpreter, all packages, data files — into a self-contained directory
(`dist/GPS Monitor/`).

Key packaging decisions in `gps_monitor.spec`:

| Package | Why special handling is needed |
|---------|-------------------------------|
| **vispy** | GLSL shader files (`.glsl`, `.vert`, `.frag`) are loaded at runtime by path, not imported. `collect_data_files('vispy')` bundles all 147 shader files. |
| **matplotlib** | Font files and style sheets in `mpl-data/` are required for any plot to render. |
| **certifi** | The CA certificate bundle (`cacert.pem`) must travel with the app so HTTPS downloads work inside the frozen bundle. |
| **folium / branca** | Jinja2 HTML templates are loaded from disk, not embedded in the `.py` files. |
| **cartopy** | Natural Earth shapefiles and projection data are copied. Coastline shapefiles are downloaded to the user's cache on first use — internet required once. |
| **PyQt6-WebEngine** | Qt WebEngine has large resource directories; PyInstaller's built-in hook handles them automatically when `PyQt6.QtWebEngineWidgets` is detected. |

### Runtime Hook (`build/runtime_hook.py`)

Executes before any app code when the bundle starts:
1. Patches `ssl._create_default_https_context` to use certifi's bundled CA file
   (avoids SSL errors when downloading TLE data or NTP queries from inside the bundle).
2. Sets `QT_PLUGIN_PATH` so PyQt6 can find its platform plugins.

### macOS `.app` Bundle

The `BUNDLE()` step in the spec wraps the collected directory into a proper
macOS application bundle with a custom `Info.plist`:

- `NSHighResolutionCapable: True` — Retina display support
- `NSRequiresAquaSystemAppearance: False` — respects Dark Mode
- `com.apple.security.network.client` entitlement — allows outbound HTTPS (TLE, NTP)
- `com.apple.security.device.serial` entitlement — allows GPS serial port access

### Windows Installer

`installer.iss` is an [Inno Setup 6](https://jrsoftware.org/isinfo.php) script that:
- Installs `dist\GPS Monitor\` to `Program Files\GPS Monitor`
- Creates Start Menu shortcuts and an optional desktop icon
- Offers to launch the app after installation
- Cleans up runtime-generated files (TLE cache, satellite database, logs) on uninstall
- Checks for the Visual C++ 2015–2022 runtime (required by Qt) and warns if missing

---

## Troubleshooting

### App fails to start on macOS ("damaged or can't be opened")
The app is ad-hoc signed (no Apple Developer ID). First-time users must:
```
Right-click the app → Open → Open
```
Or from Terminal:
```bash
xattr -cr "/Applications/GPS Monitor.app"
```

For trusted distribution to other machines, sign and notarize with an Apple
Developer ID ($99/year). Replace the `-` in the `codesign` command in
`build_mac.sh` with your certificate name.

### Gatekeeper quarantine after downloading DMG
```bash
xattr -d com.apple.quarantine /path/to/GPS\ Monitor.app
```

### Globe does not render (blank or black globe)
VisPy uses OpenGL. Some virtual machines and Remote Desktop sessions have no
GPU acceleration. The app requires at least OpenGL 2.1. Check:
```bash
python -c "import vispy; vispy.test()"
```

### "No module named 'cartopy'" inside the bundle
Run `python build/make_icons.py` before building — this also verifies the Python
environment has all dependencies. Then rebuild with `--clean`.

### Coastlines / terrain not visible on first launch
cartopy downloads Natural Earth shapefiles to `~/.local/share/cartopy/` (Linux/Windows)
or `~/Library/Caches/cartopy/` (macOS) on first use. An internet connection is
required once. After that, they are cached permanently.

### Windows: "The code execution cannot proceed because MSVCP140.dll was not found"
Install the [Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).

---

## Bundle Size

| Platform | App bundle | Installer / DMG |
|----------|-----------|-----------------|
| macOS | ~522 MB (uncompressed .app) | ~196 MB (.dmg) |
| Windows | ~500 MB (directory) | ~190 MB (.exe installer, estimated) |

The size is dominated by Qt WebEngine (~200 MB), matplotlib fonts (~50 MB), and
cartopy/shapely libraries. If WebEngine is not needed, removing the
`PyQt6-WebEngine` package and switching `WorldMapWidget` to matplotlib-only
would reduce the bundle by ~200 MB.
