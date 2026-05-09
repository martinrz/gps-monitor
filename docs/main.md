# main.py

Entry point for the GPS Monitor application.

## Responsibilities

- Patches `ssl._create_default_https_context` to use certifi's CA bundle before any network-using imports load (fixes HTTPS on macOS where system certs are not trusted by Python by default).
- Calls `utils.log_config.setup()` to configure the root logger (rotating file + WARNING-only console).
- Parses CLI arguments: `--simulate`, `--tle`, `--port`.
- Creates the `QApplication` with Fusion style and a dark `QPalette`.
- Instantiates `MainWindow`, sizes it to 92% of available screen, centres it, then defers dock-width tuning 300 ms via `QTimer.singleShot` (after Qt has finished laying out the window).

## CLI Arguments

| Argument | Effect |
|----------|--------|
| `--simulate` | Keplerian simulation mode, no hardware needed |
| `--tle` | Live TLE mode — downloads from CelesTrak on startup |
| `--port <dev>` | Connect to a specific serial port (e.g. `/dev/ttyUSB0`, `COM3`) |

If no argument is given and no serial port is found, the app falls back to simulation automatically.

## Notes

- The SSL patch **must** stay at the top of this file, before any import that may trigger a network request (cartopy downloads shapefiles on first use).
- Dock widths are set with `resizeDocks()` after a 300 ms delay because Qt does not know the final window size inside the constructor.
