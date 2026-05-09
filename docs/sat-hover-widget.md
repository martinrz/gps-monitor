# gui/sat_hover_widget.py

`SatHoverWidget(QWidget)` — compact satellite info panel shown in the right dock when the cursor is over a globe dot.

## Layout

```
[satellite name — coloured by system]
───────────────────────────────────
System   [value]   PRN      [value]
Elevation[value]   Azimuth  [value]
SNR      [value]   In fix   [value]
Sub-sat  [value]   Altitude [value]
```

The detail grid is hidden when no satellite is hovered.

## Public API

```python
widget.show_satellite(sat: SatelliteInfo | None)
```

Pass `None` to revert to the "hover over a satellite" placeholder.

## Colour Coding

- **Name / System value**: `SYSTEM_COLORS[sat.system]`
- **SNR**: green ≥ 35 dBHz, yellow ≥ 25, orange > 0, grey = 0
- **Elevation**: green > 10°, yellow > 0°, grey ≤ 0°
- **In fix**: green = Yes, grey = No

## Name Resolution

Uses `sat.name.strip()` if non-empty, otherwise falls back to `"{system} PRN {prn}"`. This means hardware receivers (where `name=""`) still show a useful label.
