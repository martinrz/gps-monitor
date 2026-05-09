# gui/satellite_table.py

`SatelliteTableWidget(QTableWidget)` — sortable satellite list.

## Columns

`PRN | System | El° | Az° | SNR (dBHz) | Used`

## Update Paths

### `apply_rows(rows)` — fast path
Accepts pre-computed tuples from `DisplayWorker`:
```python
(prn: str, system: str, el: str, az: str, snr: str, used: str,
 bg: tuple[int,int,int], fg: tuple[int,int,int])
```
Sorting is disabled while updating and re-enabled after, which avoids intermediate sort flicker.

### `update_satellites(satellites)` — legacy path
Computes colours inline via `_row_colors()`. Used if the table is driven directly without a display worker.

## Color Thresholds

| Condition | BG level | FG level |
|-----------|----------|----------|
| SNR ≥ 35 dBHz | 28% of system colour | 100% |
| SNR ≥ 25 dBHz | 18% | 85% |
| SNR > 0, el > 0 | 12% | 65% |
| Below horizon or no signal | 12% | 40% |
