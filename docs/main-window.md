# gui/main_window.py

`MainWindow(QMainWindow)` — top-level window, orchestrates all widgets and threads.

## Layout

```
┌─────────────────────────────────────────────────────┐
│  Toolbar: GPS Source selector | Connect | LED | Protocol | Terrain |
│  Toolbar: System filter buttons | Per-system satellite counts       |
├──────────────┬──────────────────────────┬────────────┤
│  Satellites  │                          │  Sky View  │
│  Table       │      Globe 3D            │  Time      │
│  (dock left) │    (central widget)      │  Hover     │
│              │                          │  (dock rt) │
├──────────────┴──────────────────────────┴────────────┤
│                  World Map (dock bottom)              │
└─────────────────────────────────────────────────────┘
```

The right dock contains a `QSplitter(Vertical)` with `SkyViewWidget`, `TimeDisplayWidget`, and `SatHoverWidget` stacked vertically.

## Thread Lifecycle

`_start_threads()` is safe to call multiple times (used when switching sources). Resources created only once (guarded by `hasattr`):
- `_display_worker` / `_display_thread` — persists across source switches
- `_ntp_thread` / `_ntp_client` — independent of GPS source
- Globe ↔ receiver signal connections

`_stop_gps()` calls `receiver.stop()`, quits the GPS thread, and waits up to 7 s. If the thread doesn't exit in time (e.g. TLE download in progress), `_park_thread()` stores a reference in `_dying_threads` to prevent Qt's GC-triggered `abort()`.

## `_on_prepared(frame: PreparedFrame)`

The main UI update handler. Called on the main thread via `QueuedConnection`:
1. Updates LED indicator to green.
2. Updates protocol badge.
3. Calls `globe.apply_prepared(...)` — fast numpy set_data.
4. Calls `sat_table.apply_rows(...)` — fast QTableWidget update.
5. If `frame.update_sky`: calls `sky_view.update_satellites(...)`.
6. Updates `time_display` GPS time.
7. Updates per-system satellite count labels.
8. If fix available: updates world map and status bar.

## Constellation Toolbar

Each system button is a checkable `QPushButton` styled with the system colour. Toggling calls `receiver.set_constellations()` immediately. "All" / "None" buttons block signals while updating all buttons to avoid redundant calls.

## Observer Position

Three event sources update the observer:
- Right-click drag on the globe → `observer_moved` signal
- Click on the folium map → `location_clicked` signal
- Both route to `_on_observer_moved()` which updates globe, map, and receiver simultaneously.

## `_park_thread(thread)`

Appends `thread` to `_dying_threads`; connects `thread.finished` to a lambda that removes it when done. Prevents the Python GC from destroying a `QThread` C++ object that is still running (which triggers Qt's `abort()`).
