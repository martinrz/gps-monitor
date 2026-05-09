# gui/globe_3d.py

`Globe3DWidget(QWidget)` — VisPy-based interactive 3D globe.

## Signals

| Signal | Payload | Trigger |
|--------|---------|---------|
| `observer_moved` | `(float, float)` lat/lon | Right-click drag released |
| `satellite_selected` | `SatelliteInfo` | Double-click near a satellite |
| `satellite_hovered` | `SatelliteInfo \| None` | Mouse move over/away from a dot |

## Scene Composition (insertion order)

1. Ocean sphere (`Sphere`, translucent, `depth_test=True`, `cull_face=False`)
2. Graticule lines (30° spacing)
3. Equator line
4. Coastlines (cartopy Natural Earth 110m, downloaded on first use)
5. `_sat_visual` (`Markers`, `depth_test=False`)
6. `_obs_marker` (`Markers`, `depth_test=False`, yellow star)
7. `_terrain_mesh` (added dynamically, then markers re-parented after it)

`depth_test=False` on markers is essential: it makes satellites visible on both hemispheres regardless of the Earth's opaque depth buffer. When terrain is enabled, markers are re-parented to the tail of the scene so they always paint over the terrain mesh (VisPy renders children in insertion order).

## Satellite Update Paths

- **`apply_prepared(positions, colors, satellites)`** — fast path called from `MainWindow._on_prepared()`. Accepts pre-computed numpy arrays from `DisplayWorker`; no per-satellite loop on the main thread.
- **`update_satellites(satellites)`** — legacy path; computes positions and colours inline. Still works; bypassed in normal operation.

## Hover Detection (`_detect_hover`)

Screen-space projection approach:
1. Get the `'visual' → 'canvas'` transform from `_sat_visual`.
2. Map all `_current_positions` (N×4 homogeneous) through the transform to get canvas-space (x, y, w).
3. Discard satellites with `w ≤ 0` (behind the camera).
4. Compute 2D Euclidean distance from cursor to each projected point.
5. Select the nearest satellite; emit it if distance < 12 pixels, else emit `None`.

This correctly handles satellites at any visual radius (LEO at 1.12, GEO at 2.25) because it matches actual screen pixels, not angular distances on the globe surface.

## Observer Dragging (`_on_mouse_press`, `_on_mouse_move`)

Right-click (button=2) within 24 pixels of the observer marker starts a drag. Mouse moves call `_screen_to_sphere()` to ray-cast the cursor onto the Earth surface (radius=1.0) and update the observer position. On release, `observer_moved` is emitted.

## Terrain Toggle (`toggle_terrain`)

Enabled:
1. `_make_earth_texture()` renders a 2048×1024 RGBA image via cartopy/matplotlib (first call only; result cached in `_terrain_texture`).
2. A `Mesh` sphere is created and a `TextureFilter` is attached with computed UV coordinates (derived from vertex lat/lon since VisPy `MeshData` has no `get_texcoords()`). Image rows are flipped (`[::-1]`) to match OpenGL's bottom-origin convention.
3. The ocean sphere is hidden.
4. Marker visuals are re-parented to end of scene.

Disabled: terrain mesh is un-parented; ocean sphere is shown again.

## Camera

`TurntableCamera`, initial elevation 20°, azimuth 30°, distance 4.5, FOV 40°.
