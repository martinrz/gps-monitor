# gui/time_display.py

`TimeDisplayWidget(QWidget)` — live time panel in the right dock.

## Displayed Values

| Label | Source | Update rate |
|-------|--------|------------|
| System UTC | `time.gmtime()` | 100 ms QTimer |
| GPS Time | Latest `GPSData.gps_time` | Each GPS frame (~1 Hz) |
| GPS Date | Latest `GPSData.gps_date` | Each GPS frame |
| NTP Time | `TimeEstimate.utc_time` | Every ~30 s (NTPClient interval) |
| NTP Uncertainty | `TimeEstimate.uncertainty_ms` | Every ~30 s |
| NTP Servers | `TimeEstimate.contributing_servers` | Every ~30 s |
| GPS-NTP Offset | `TimeEstimate.gps_offset_ms` | Every ~30 s |

## Public API

```python
widget.update_gps_time(gps_time: str | None, gps_date: str | None)
widget.update_time_estimate(estimate: TimeEstimate)
```

Both are called from `MainWindow._on_prepared()` and `MainWindow._on_time_update()` respectively.
