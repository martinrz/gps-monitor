# gui/world_map.py

`WorldMapWidget(QWidget)` — 2D world map showing observer position.

## Signal

`location_clicked(float, float)` — emitted when the user clicks the map (lat, lon).

## Render Mode

Selected at construction time based on available packages:

| Mode | Requirements | Notes |
|------|-------------|-------|
| `folium` | PyQt6-WebEngine + folium | Interactive HTML map in `QWebEngineView` |
| `matplotlib` | Always available | Static equirectangular plot |

## Folium Mode

Map is rebuilt as HTML each time `update_position()` is called (throttled to every `THROTTLE_S = 2.0` seconds). A green `CircleMarker` marks the observer.

Click handling: JavaScript injected via `page().runJavaScript()` after each page load wires a Leaflet `map.on('click')` handler. Clicks set `document.title` to `GPS_CLICK:<lat>:<lon>`, which Qt's `titleChanged` signal delivers to `_on_title_changed()` on the Python side.

Terrain/satellite imagery toggle switches the tile layer between CartoDB dark matter and ESRI World Imagery.

## Throttle

`update_position()` checks `time.time() - _last_update` before rebuilding the map. Position is always stored in `_lat`/`_lon` regardless, so terrain-mode switches use the latest known position.
