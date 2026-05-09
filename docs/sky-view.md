# gui/sky_view.py

`SkyViewWidget(QWidget)` — polar matplotlib plot showing satellites relative to the observer's horizon.

## Plot Convention

- **North up**, clockwise (compass bearing).
- Radial axis: 0° at zenith (centre), 90° at horizon (edge). Tick labels show 60°/30°/0° elevation.
- Each satellite is a scatter dot sized by `max(40, snr × 2.5)` and coloured by `SYSTEM_COLORS`.
- Alpha: 1.0 if SNR ≥ 25 dBHz, 0.55 if weaker.
- PRN number annotated in white at 3,3 pixel offset.

## `update_satellites(satellites)`

Clears and redraws the axes on each call. Only satellites with `elevation ≥ 0` are plotted.  
Throttled by `DisplayWorker` to at most 1 Hz — receives an empty list when the sky update is skipped.
