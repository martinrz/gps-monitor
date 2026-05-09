# gps/receiver.py

`GPSReceiver(QObject)` — central data source, runs on a dedicated `QThread`.

## Signals

| Signal | Payload | Description |
|--------|---------|-------------|
| `data_ready` | `GPSData` | Emitted ~1 Hz with a complete satellite snapshot |
| `status_changed` | `str` | Human-readable status message for the status bar |
| `error_occurred` | `str` | Protocol read error |

## Slots

| Slot | Description |
|------|-------------|
| `set_constellations(systems)` | Enable/disable systems at runtime; forwarded to the active simulator |
| `set_location(lat, lon)` | Move the observer; forwarded to the active simulator |

## Startup Modes

`run()` dispatches based on the constructor arguments:

1. **TLE mode** (`use_tle=True`) — calls `_run_tle_mode()`: creates a `TLESimulator`, calls `preload()` with a `stop_check` lambda, then loops calling `get_gps_data()` every second.
2. **Simulation** (`simulate=True` or no serial available) — creates a `GPSSimulator` and loops.
3. **Serial / auto-detect** — scans all discovered COM ports at baud rates 9600/4800/38400/115200. Reads 3 s of data at each setting and inspects for protocol magic bytes: NMEA `$GP`/`$GN`/`$GL`, UBX `\xB5\x62`, SiRF `\xA0\xA2`. Falls back to simulation if nothing is found.

## Protocol Dispatch

Once a protocol is detected, the receiver enters a dedicated read loop:
- `_read_loop_nmea()` — reads lines, feeds to `NMEAParser.feed()`
- `_read_loop_ubx()` — reads 1024-byte chunks, feeds to `UBXParser.feed_bytes()`
- `_read_loop_sirf()` — reads 256-byte chunks, feeds to `SiRFParser.feed_bytes()`

## Thread Safety

`stop()` sets `_running = False` and closes the serial port. The loops check `_running` on every iteration, so shutdown is prompt.
