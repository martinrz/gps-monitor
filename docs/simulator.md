# gps/simulator.py

`GPSSimulator` — multi-constellation GNSS simulator using Keplerian orbital mechanics.  
No network access, no hardware required. All positions are computed from a hardcoded almanac.

## Constellation Almanac (`FULL_ALMANAC`)

Built once at import time by `_build_almanac()`:

| System | Sats | Orbital parameters |
|--------|------|--------------------|
| GPS | 31 | 6 planes, SMA 26,560 km, inc 55° |
| GLONASS | 24 | 3 planes, SMA 25,508 km, inc 64.8° |
| Galileo | 27 | 3 planes, SMA 29,600 km, inc 56° |
| BeiDou MEO | 27 | 3 planes, SMA 27,906 km, inc 55° |
| BeiDou IGSO | 3 | GEO altitude, inc 55° |
| BeiDou GEO | 5 | Truly geostationary, inc 0° |
| QZSS | 4 | 3 IGSO + 1 GEO, covering Japan/Asia-Pacific |
| NavIC | 7 | 3 GEO + 4 IGSO, covering India/South Asia |
| Starlink | 100 | Shell 1: 550 km, inc 53°, 20 planes × 5 sats |

Each row: `(system, prn, sma_m, ecc, inc_deg, raan_deg, arg_perigee_deg, mean_anomaly_deg)`.

## Public API

```python
sim = GPSSimulator(lat=51.5, lon=-0.12, alt=10.0)
sim.set_enabled_systems({'GPS', 'GALILEO'})
sim.set_location(37.7749, -122.4194)
data: GPSData = sim.get_gps_data()
```

## SNR Model

Visible satellites (elevation > 0): `SNR = 20 + elevation × 0.4 + N(0, 1.5)`, clamped to [15, 52] dBHz.  
Below-horizon satellites: SNR = 0.

## Coordinate Pipeline

For each satellite, per call to `get_gps_data()`:
1. `keplerian_to_ecef()` — propagate from current GPS time
2. `ecef_to_azel()` — compute elevation and azimuth from observer
3. `ecef_to_latlon()` — compute sub-satellite lat/lon/altitude

The GPS week clock (`gps_t`) is computed as `(unix_time − GPS_EPOCH) % (7 × 86400)`.
